"""Functionality for onboarding a new save state"""
from pathlib import Path
from typing import Iterable

from git import Repo

from .manifest import Manifest


def create_repo(
    repo_root: Path, *patterns: Iterable[str], ignore: Iterable[str] | None = None
) -> tuple[Repo, Manifest]:
    """Create a new gsb-managed git repo in the specified location

    Parameters
    ----------
    repo_root : Path
        The directory where the repo should be created.
    patterns : str
        List of glob-patterns to match, specifying what in the working directory
        should be archived. If none are provided, then it will be assumed that
        the intent is to back up the *entire* folder and all its contents
    ignore : list of str, optional
        List of glob-patterns to *ignore*. If None are specified, then nothing
        will be ignored.

    Returns
    -------
    Repo
        The newly-created repo

    Raises
    ------
    ValueError
        If the repo root is not a directory
    FileNotFoundError
        If the repo root does not exist
    FileExistsError
        If there is already a git repo in that location
    """
    raise NotImplementedError
