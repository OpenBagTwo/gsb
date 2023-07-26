"""Functionality for restoring to an old backup"""
import logging
from pathlib import Path

from . import _git, backup
from .logging import IMPORTANT

LOGGER = logging.getLogger(__name__)


def restore_backup(repo_root: Path, revision: str) -> str:
    """Rewind to a previous backup state and create a new backup

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    revision : str
        The commit hash or tag name of the backup to restore

    Returns
    -------
    str
        The tag name of the new restored backup

    Notes
    -----
    Before creating the backup, any un-backed up changes will first be backed up

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a gsb-managed repo
    ValueError
        If the specified revision does not exist
    """
    _git.show(repo_root, revision)

    LOGGER.log(
        IMPORTANT, "Backing up any unsaved changes before rewinding to %s", revision
    )
    orig_head = backup.create_backup(
        repo_root, f"Backing up state before rewinding to {revision}"
    )

    _git.reset(repo_root, revision, hard=True)
    _git.reset(repo_root, orig_head, hard=False)

    return backup.create_backup(repo_root, f"Restored to {revision}")
