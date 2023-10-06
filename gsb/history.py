"""Functionality for tracking and managing revision history"""
import datetime as dt
import logging
from pathlib import Path
from typing import Any, TypedDict

from . import _git
from .logging import IMPORTANT

LOGGER = logging.getLogger(__name__)


class Revision(TypedDict):
    """Metadata on a GSB-managed version

    Parameters
    ----------
    identifier : str
        A short, unique identifier for the revision
    commit_hash : str
        The full hexadecimal hash associated with the revision
    description : str
        A description of the version
    timestamp : dt.datetime
        The time at which the version was created
    tagged : bool
        Whether or not this is a tagged revision
    gsb : bool
        Whether or not this is a GSB-created revision
    """

    identifier: str
    commit_hash: str
    description: str
    timestamp: dt.datetime
    tagged: bool
    gsb: bool


def get_history(
    repo_root: Path,
    tagged_only: bool = True,
    include_non_gsb: bool = False,
    limit: int = -1,
    since: dt.date = dt.datetime(1970, 1, 1),
    since_last_tagged_backup: bool = False,
) -> list[Revision]:
    """Retrieve a list of GSB-managed versions

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    tagged_only : bool, optional
        By default, this method only returns tagged backups. To include
        all available revisions, pass in `tagged_only=False`.
    include_non_gsb : bool, optional
        By default, this method excludes any revisions created outside of `gsb`.
        To include all git commits and tags, pass in `include_non_gsb=True`.
    limit : int, optional
        By default, this method returns the entire history. To return only the
        last _n_ revisions, pass in `limit=n`.
    since : date or timestamp, optional
        By default, this method returns the entire history. To return only
        revisions made on or after a certain date, pass in `since=<start_date>`.
    since_last_tagged_backup: bool, optional
        False by default. To return only revisions made since the last tagged
        backup, pass in `since_last_tagged_backup=True` (and, presumably,
        `tagged_only=False`). This flag is compatible with all other filters.

    Returns
    -------
    list of dict
        metadata on the requested revisions, sorted in reverse-chronological
        order

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a git repo
    """
    tag_lookup = {
        tag.target: tag for tag in _git.get_tags(repo_root, annotated_only=True)
    }
    LOGGER.debug("Retrieved %s tags", len(tag_lookup))

    revisions: list[Revision] = []
    for commit in _git.log(repo_root):
        if len(revisions) == limit:
            break
        if commit.timestamp < since:
            break
        if tag := tag_lookup.get(commit):
            if since_last_tagged_backup:
                break
            tagged = True
            identifier = tag.name
            is_gsb = tag.gsb if tag.gsb is not None else commit.gsb
            description = tag.annotation or commit.message
        else:
            if tagged_only:
                continue
            tagged = False
            identifier = commit.hash[:8]
            is_gsb = commit.gsb
            description = commit.message
        if not include_non_gsb and not is_gsb:
            continue
        revisions.append(
            {
                "identifier": identifier,
                "commit_hash": commit.hash,
                "description": description.strip(),
                "timestamp": commit.timestamp,
                "tagged": tagged,
                "gsb": is_gsb,
            }
        )
    return revisions


def log_revision(revision: Revision, idx: int | None) -> None:
    """Print (log) a revision

    Parameters
    ----------
    revision : dict
        Metadata for the revision
    idx : int | None
        The index to give to the revision. If None is specified, the revision
        will be displayed with a "-" instead of a numbering.

    Notes
    -----
    - The version identifiers and dates are logged at the IMPORTANT (verbose=0) level
    - The version descriptions are logged at the INFO (verbose=1) level
    - The full version hashes are logged at the DEBUG (verbose=2) level
    """
    args: list[Any] = [revision["identifier"], revision["timestamp"].isoformat("-")]
    if idx is None:
        format_string = "- %s from %s"
    else:
        format_string = "%d. %s from %s"
        args.insert(0, idx)

    LOGGER.log(IMPORTANT, format_string, *args)

    LOGGER.debug("Full reference: %s", revision["commit_hash"])
    LOGGER.info("%s", revision["description"])


def show_history(
    repo_root: Path,
    numbering: int | None = 1,
    **kwargs,
) -> list[Revision]:
    """Fetch and print (log) the list of versions for the specified repo matching
    the given specs

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    numbering: int or None, optional
        When displaying the versions, the default behavior is to number the
        results, starting at 1. To set a different starting number, provide that.
        To use "-" instead of numbers, pass in `numbering=None`.
    **kwargs
        Any other options will be passed directly to `get_history()`
        method

    Notes
    -----
    See `log_revision()` for details about what information is logged to each
    log level

    Returns
    -------
    list of dict
        metadata on the requested revisions, sorted in reverse-chronological
        order

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a git repo
    """
    history = get_history(repo_root, **kwargs)
    for i, revision in enumerate(history):
        log_revision(revision, i + numbering if numbering is not None else None)
    return history
