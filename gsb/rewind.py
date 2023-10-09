"""Functionality for restoring to an old backup"""
import logging
from pathlib import Path

from . import _git, backup
from .logging import IMPORTANT

LOGGER = logging.getLogger(__name__)


def generate_restore_tag_name(revision: str) -> str:
    """Generate a new calver-ish tag name

    Parameters
    ----------
    revision : str
        The commit hash or tag name of the backup to restore

    Returns
    -------
    str
        A tag name that indicates both the time a backup was restored and the
        identifier of the original revision
    """
    return f"{backup.generate_tag_name()}.restore_of_{revision}"


def restore_backup(repo_root: Path, revision: str, keep_gsb_files: bool = True) -> str:
    """Rewind to a previous backup state and create a new backup

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    revision : str
        The commit hash or tag name of the backup to restore
    keep_gsb_files : bool, optional
        By default, `.gsb_manifest` and `.gitignore` *will not* be restored
        (that is, the latest versions will be kept). To override this behavior,
        pass in `keep_gsb_files = False`.

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
    if keep_gsb_files:
        _git.checkout_files(repo_root, orig_head, backup.REQUIRED_FILES)
    return backup.create_backup(
        repo_root,
        f"Restored to {revision}",
        tag_name=generate_restore_tag_name(revision),
    )
