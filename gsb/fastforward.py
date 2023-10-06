"""Functionality for removing backups from a repo's history"""
import datetime as dt
import logging
from pathlib import Path

from . import _git, backup
from .logging import IMPORTANT

LOGGER = logging.getLogger(__name__)


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
    *revisions: str
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
    _ = _git.show(repo_root, starting_point)  # ensure starting point is valid
    tag_lookup = {
        tag.target: tag for tag in _git.get_tags(repo_root, annotated_only=False)
    }
    new_history: list[_git.Tag | _git.Commit] = []

    for reference in revisions:
        revision: _git.Tag | _git.Commit = _git.show(repo_root, reference)
        if revision in tag_lookup.keys():
            revision = tag_lookup[revision]  # type: ignore[index]
        new_history.append(revision)

    try:
        head = backup.create_backup(repo_root)
        LOGGER.log(IMPORTANT, "Unsaved changes have been backed up as %s", head[:8])
        new_history.append(_git.show(repo_root, head))
    except ValueError:
        # nothing to back up
        pass

    try:
        branch_name = dt.datetime.now().strftime("gsb_rebase_%Y.%m.%d+%H%M%S")
        _git.checkout_branch(repo_root, branch_name, starting_point)
        head = starting_point
        tags_to_update: list[tuple[_git.Tag, str]] = []
        for revision in new_history:
            match revision:
                case _git.Commit():
                    _git.reset(repo_root, revision.hash, hard=True)
                    _git.reset(repo_root, head, hard=False)
                    new_hash = _git.commit(
                        repo_root,
                        message=(
                            revision.message + "\n\n" + f"rebase of {revision.hash}"
                        ),
                        timestamp=revision.timestamp,
                    ).hash
                    head = new_hash
                case _git.Tag():
                    _git.reset(repo_root, revision.target.hash, hard=True)
                    _git.reset(repo_root, head, hard=False)
                    new_hash = _git.commit(
                        repo_root,
                        message=(
                            (revision.annotation or revision.name)
                            + "\n\n"
                            + f"rebase of {revision.target.hash}"
                            + f' ("{revision.target.message.strip()}")'
                        ),
                        timestamp=revision.target.timestamp,
                    ).hash
                    tags_to_update.append((revision, new_hash))
                    head = new_hash
                case _:  # pragma: no cover
                    raise NotImplementedError(
                        f"Don't know how to handle revision of type {type(revision)}"
                    )
        for tag, target in tags_to_update:
            _git.delete_tag(repo_root, tag.name)
            _git.tag(repo_root, tag.name, tag.annotation, target=target)
        try:
            _git.delete_branch(repo_root, "gsb")
        except ValueError as delete_fail:
            # this can happen if you onboarded an existing repo to gsb, in
            # which case the active branch won't necessarily be gsb
            LOGGER.warning("Could not delete branch %s:\n    %s", "gsb", delete_fail)
        _git.checkout_branch(repo_root, "gsb", head)
        return head
    except Exception as something_went_wrong:  # pragma: no cover
        _git.reset(repo_root, head, hard=True)
        raise something_went_wrong
    finally:
        _git.checkout_branch(repo_root, "gsb", None)
        _git.delete_branch(repo_root, branch_name)


def delete_backups(repo_root: Path, *revisions: str) -> str:
    """Delete the specified backups

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    *revisions : str
        The commit hashes and tag names of the backups to delete

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
    - Deleting the initial backup is not currently supported.

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a gsb-managed repo
    ValueError
        If the specified revision does not exist
    """
    to_delete: dict[_git.Commit, str] = {}
    for revision in revisions:
        match reference := _git.show(repo_root, revision):
            case _git.Commit():
                # keep the link back to the revision in case we need to raise
                # an error about it later
                to_delete[reference] = revision
            case _git.Tag():
                to_delete[reference.target] = revision
            case _:  # pragma: no cover
                raise NotImplementedError(f"Don't know how to handle {type(reference)}")

    to_keep: list[str] = []
    for commit in _git.log(repo_root):
        if commit in to_delete.keys():
            del to_delete[commit]
        else:
            to_keep.insert(0, commit.hash)
            if len(to_delete) == 0:
                break
    else:
        if len(to_delete) == 0:
            raise NotImplementedError(
                "Deleting the initial backup is not currently supported."
            )
        else:
            raise ValueError(
                "The following revisions exist, but they are not within"
                " the linear commit history:\n"
                + "\n".join((f"  - {revision}" for revision in to_delete.values()))
            )
    return rewrite_history(repo_root, *to_keep)
