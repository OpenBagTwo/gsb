"""Functionality for creating backups"""
import datetime as dt
import logging
from pathlib import Path

from . import _git
from .logging import IMPORTANT
from .manifest import MANIFEST_NAME, Manifest

REQUIRED_FILES: tuple[Path, ...] = (Path(".gitignore"), Path(MANIFEST_NAME))

LOGGER = logging.getLogger(__name__)


def _generate_tag_name() -> str:
    """Generate a new calver-ish tag name

    Returns
    -------
    str
        A tag name that should hopefully be distinctly gsb and distinct
        from any tags a user would manually create

    Notes
    -----
    When unit testing, this method will need to be monkeypatched to provide
    even greater granularity... unless you want to use `time.sleep(1)` between
    each tag :O
    """
    return dt.datetime.now().strftime("gsb%Y.%m.%d+%H%M%S")


def create_backup(repo_root: Path, tag: str | None = None) -> str:
    """Create a new backup

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    tag : str, optional
        By default, this method just creates an "untagged" backup with a default
        commit message. To tag this backup, provide a description of the backup
        to use for both the commit message and the tag annotation.

    Returns
    -------
    str
        An identifier for the backup in the form of either a commit hash or a
        tag name

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a gsb-managed repo
    ValueError
        If there are no changes to commit and no tag message was provided
    """
    manifest = Manifest.of(repo_root)
    _git.add(repo_root, manifest.patterns)
    _git.force_add(repo_root, REQUIRED_FILES)
    try:
        identifier = _git.commit(repo_root, tag or "Manual backup").hash
        logging.info(f"Changes committed with hash %s", identifier)
    except ValueError:
        if not tag:
            raise
        logging.info("Nothing new to commit--all files are up-to-date.")
    if tag:
        identifier = _git.tag(repo_root, _generate_tag_name(), tag).name
        logging.log(IMPORTANT, "Created new tagged backup: %s", identifier)
    return identifier
