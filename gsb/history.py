"""Functionality for tracking and managing revision history"""
import datetime as dt
import logging
from pathlib import Path
from typing import TypedDict

from . import _git
from .logging import IMPORTANT

LOGGER = logging.getLogger(__name__)


class _Revision(TypedDict):
    """Metadata on a GSB-managed version

    Parameters
    ----------
    identifier : str
        A unique identifier for the revision
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
    numbering: int | None = 1,
) -> list[_Revision]:
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
    numbering: int or None, optional
        When displaying the versions, the default behavior is to number the
        results, starting at 1. To set a different starting number, provide that.
        To use "-" instead of numbers, pass in `numbering=None`.

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

    revisions: list[_Revision] = []
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
        if numbering is None:
            LOGGER.log(
                IMPORTANT,
                "- %s from %s",
                tag.name if tag else commit.hash[:8],
                commit.timestamp.isoformat("-"),
            )
        else:
            LOGGER.log(
                IMPORTANT,
                "%d. %s from %s",
                len(revisions) + numbering,
                tag.name if tag else commit.hash[:8],
                commit.timestamp.isoformat("-"),
            )
        LOGGER.debug("Full reference: %s", commit.hash)
        LOGGER.info("%s", description)
        revisions.append(
            {
                "identifier": identifier,
                "description": description.strip(),
                "timestamp": commit.timestamp,
                "tagged": tagged,
                "gsb": is_gsb,
            }
        )
    return revisions
