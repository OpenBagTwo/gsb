"""Abstraction around the git library interface (to allow for easier backend swaps"""
import getpass
from pathlib import Path
from typing import Iterable

import pygit2


def init(repo_root: Path) -> None:
    """Initialize (or re-initialize) a git repo, equivalent to running
    `git init`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo

    Raises
    ------
    ValueError
        If `repo_root` is not a directory
    OSError
        If `repo_root` does not exist or cannot be accessed
    """
    _repo(repo_root, new=True)


def _repo(repo_root: Path, new: bool = False) -> pygit2.Repository:
    """Load a git repository from the specified location

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    new : bool, optional
        By default, this method loads existing repositories. To initialize a new
        repo, pass in `new=True`

    Returns
    -------
    repo
        The requested git repository

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
    if new:
        return pygit2.init_repository(repo_root)
    return pygit2.Repository(repo_root)


def _config() -> dict[str, str]:
    """Load the global git config and fill in any missing needed values

    Returns
    -------
    dict
        The user's global git config settings

    Notes
    -----
    Loading a repo-specific git config is not supported by this method
    """
    try:
        config: dict[str, str] = {
            entry.name: entry.value for entry in pygit2.Config().get_global_config()
        }
    except OSError:
        config = {}

    config["user.name"] = config.get("user.name") or getpass.getuser()
    if "user.email" not in config:
        config["user.email"] = ""

    config["committer.name"] = "gsb"
    config["committer.email"] = ""
    return config


def add(repo_root: Path, files: Iterable[str | Path], force: bool) -> None:
    """Add files matching the given pattern to the repo, equivalent to running
    `git add <pattern>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    files : list of str or path
        The file paths to add. When `force=False` this also supports glob
        patterns.
    force : bool
        Whether to override `.gitignore`

    Raises
    ------
    ValueError
        If `repo_root` is not a directory
    FileNotFoundError
        If `force=True` and the force-added file does not exist
    IsADirectoryError
        If `force=True` and one of the specified files is a directory
    OSError
        If `repo_root` does not exist or cannot be accessed

    Notes
    -----
    """
    repo = _repo(repo_root)
    if force:
        for path in files:
            try:
                repo.index.add(path)
            except OSError as maybe_file_not_found:
                if "No such file or directory" in str(maybe_file_not_found):
                    raise FileNotFoundError(maybe_file_not_found)
                raise
            except pygit2.GitError as maybe_directory:
                if "is a directory" in str(maybe_directory):
                    raise IsADirectoryError(maybe_directory)
    else:
        repo.index.add_all(list(files))
    repo.index.write()


def commit(repo_root: Path, message: str) -> None:
    """Commit staged changes

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    message : str
        The commit message

    Raises
    ------
    ValueError
        If `repo_root` is not a directory
    OSError
        If `repo_root` does not exist or cannot be accessed
    """
    repo = _repo(repo_root)
    try:
        ref = repo.head.name
        parents = repo.head.target
    except pygit2.GitError as headless:
        if "reference 'refs/heads/main' not found" in str(headless):
            ref = "HEAD"
            parents = []
        else:
            raise

    config = _config()
    author = pygit2.Signature(config["user.name"], config["user.email"])
    committer = pygit2.Signature(config["committer.name"], config["committer.email"])
    repo.create_commit(
        ref, author, committer, message, repo.index.write_tree(), parents
    )
