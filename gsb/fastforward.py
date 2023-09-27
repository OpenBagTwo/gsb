"""Functionality for removing backups from a repo's history"""
from pathlib import Path

from . import history


def rewrite_history(repo_root: Path, starting_point: str, *revisions: str) -> str:
    """Rewrite the repo's history by only including the specified backups,
    effectively deleting the ones in between

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    starting_point: str
        The commit hash or tag name to start revising from (all prior backups
        will be kept)
    *revisions: strs
        The commit hashes / tag names for the backups that should be included
        / kept in the new history

    Returns
    -------
    str
        The tag name or commit hash for the most recent backup in the rewritten
        history

    Notes
    -----
    - The current repo state will always be kept (and, in the case that there
      are un-backed-up changes, those changes will be backed up before the
      history is rewritten).
    - The ordering of the provided revisions is not checked in advance, nor is
      anything done to check for duplicates. Providing the backups out-of-order
      will create a new history that frames the backups in the order provided.

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a gsb-managed repo
    ValueError
        If any of the specified revisions do not exist
    """
    # 1. Check for unsaved changes (and create tagged backup if there are any)
    # 2. Verify that all revisions are valid (and figure out which ones are tags)
    # 3. Check out new rebasing branch @ starting point
    # 4. FF to each backup (git reset --hard rev && git reset --soft head
    #    && gsb backup [--tag orig-tag-name])
    # 5. Once all backups have been played through successfully, update gsb/HEAD
    #    to point to new HEAD
    # 6. Delete rebasing branch
    raise NotImplementedError


def delete_backup(repo_root: Path, revision: str) -> str:
    """Delete the specified backup

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    revision : str
        The commit hash or tag name of the backup to delete

    Returns
    -------
    str
        The tag name or commit hash for the most recent backup in the rewritten
        history

    Notes
    -----
    - The current repo state will always be kept (and, in the case that there
      are un-backed-up changes, those changes will be backed up before the
      history is rewritten).

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a gsb-managed repo
    ValueError
        If the specified revision does not exist
    """
    # TODO: only pull as far back as the specified revision + 1
    revisions = history.get_history(repo_root, tagged_only=False, include_non_gsb=True)
    for i, rev in enumerate(revisions):
        if revision == rev["identifier"] or (
            revision == rev["identifier"][:8] and not revision.startswith("gsb")
        ):
            try:
                return rewrite_history(
                    repo_root,
                    revisions[i + 1]["identifier"],
                    *[revisions[j]["identifier"] for j in range(i - 1, -1, -1)],
                )
            except IndexError as thats_the_first:
                raise NotImplementedError(
                    "Deleting the first revision is not currently supported."
                )
    raise ValueError(
        f"Could not find a backup named {revision}."
        "\nRun gsb history to get a list of valid backups."
    )
