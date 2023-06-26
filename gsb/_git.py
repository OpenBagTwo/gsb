"""Abstraction around the git library interface (to allow for easier backend swaps"""
from pathlib import Path

from git import Repo


def init(repo_root: Path) -> None:
    """Initialize (or re-initialize) a git repo, equivalent to running `git init`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo

    Returns
    -------
    None

    Raises
    ------
    ValueError
        If `repo_root` is not a directory
    OSError
        If `repo_root` does not exist or cannot be accessed
    """
    repo_root = repo_root.expanduser().resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"{repo_root} does not exist")
    if not repo_root.is_dir():
        raise ValueError(f"{repo_root} is not a directory")
    Repo.init(repo_root, mkdir=False)
