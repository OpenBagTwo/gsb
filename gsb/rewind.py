"""Functionality for restoring to an old backup"""

import logging
from pathlib import Path

from . import _git, backup, manifest
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


def restore_backup(
    repo_root: Path, revision: str, keep_gsb_files: bool = True, hard: bool = False
) -> str:
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
    hard : bool, optional
        By default, any backups after the specified revision will be kept in
        the history (with the specified restore point just copied to the top
        of the stack). If you want to *fully erase* all progress after the
        restore point (backed up or loose), pass in `hard = True` and then run
        `git gc --aggressive --prune=now` afterward.

    Returns
    -------
    str
        The name of the restored backup

    Notes
    -----
    - Before creating the backup, any un-backed up changes will first be backed up
      unless `hard = True` is specified.
    - When restoring with `hard = True`, **unsaved changes** to `.gsb_manifest`
      and `.gitignore` will **not** be kept, even with `keep_gsb_files = True`.
      Instead, the restored backup will contain the GSB files from the most
      recent backup (tagged or otherwise).

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a GSB-managed repo
    ValueError
        If the specified revision does not exist
    """
    _git.show(repo_root, revision)  # ensure revision exists

    orig_head = _git.show(repo_root, "HEAD").hash  # type: ignore[union-attr]

    if hard:
        _git.add(repo_root, manifest.Manifest.of(repo_root).patterns)
    else:
        LOGGER.log(
            IMPORTANT, "Backing up any unsaved changes before rewinding to %s", revision
        )
        try:
            orig_head = backup.create_backup(
                repo_root,
                f"Backing up state before rewinding to {revision}",
            )
        except ValueError:  #  nothing to back up
            pass

    _git.reset(repo_root, revision, hard=True)
    if keep_gsb_files:
        _git.checkout_files(repo_root, orig_head, backup.REQUIRED_FILES)
    if hard:
        try:  # on the off chance that the gsb files changed, commit them
            backup.create_backup(
                repo_root, commit_message="Cherry-picking changes to the gsb files"
            )
        except ValueError:  # this is actually the more likely outcome
            pass
        return revision

    _git.reset(repo_root, orig_head, hard=False)
    return backup.create_backup(
        repo_root,
        f"Restored to {revision}",
        tag_name=generate_restore_tag_name(revision),
    )
