"""Abstraction around the git library interface (to allow for easier backend swaps"""
import datetime as dt
import getpass
import socket
from pathlib import Path
from typing import Iterable, NamedTuple

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
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
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
    NotADirectoryError
        If `repo_root` is not a directory
    FileNotFoundError
        If `repo_root` does not exist
    OSError
        If `repo_root` cannot otherwise be accessed
    """
    repo_root = repo_root.expanduser().resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"{repo_root} does not exist")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"{repo_root} is not a directory")
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
    config = _git_config()
    config["user.name"] = config.get("user.name") or getpass.getuser()
    if "user.email" not in config:
        config["user.email"] = f"{getpass.getuser()}@{socket.gethostname()}"

    config["committer.name"] = "gsb"
    config["committer.email"] = "gsb@openbagtwo.github.io"
    return config


def _git_config() -> dict[str, str]:  # pragma: no cover
    """Separate encapsulation for the purposes of monkeypatching"""
    try:
        return {
            entry.name: entry.value for entry in pygit2.Config().get_global_config()
        }
    except OSError:
        return {}


def add(repo_root: Path, patterns: Iterable[str]) -> None:
    """Add files matching the given pattern to the repo, equivalent to running
    `git add <pattern>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    patterns : list of str
        The glob patterns to match

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    repo.index.add_all(list(patterns))
    repo.index.write()


def force_add(repo_root: Path, files: Iterable[Path]) -> None:
    """Forcibly add specific files, overriding .gitignore, equivalent to running
    `git add <file> --force`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    files : list of paths
        The file paths to add, relative to the repo root

    Raises
    ------
    FileNotFoundError
        If one of the specified paths does not exist
    IsADirectoryError
        If one of the specified paths is a directory
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    for path in files:
        try:
            repo.index.add(path)
        except OSError as maybe_file_not_found:  # pragma: no cover
            if "No such file or directory" in str(maybe_file_not_found):
                raise FileNotFoundError(maybe_file_not_found)
            raise  # pragma: no cover
        except pygit2.GitError as maybe_directory:  # pragma: no cover
            if "is a directory" in str(maybe_directory):
                raise IsADirectoryError(maybe_directory)
    repo.index.write()


def commit(repo_root: Path, message: str) -> None:
    """Commit staged changes, equivalent to running `git commit -m <message>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    message : str
        The commit message

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    try:
        ref = repo.head.name
        parents = [repo.head.target]
    except pygit2.GitError as headless:
        if "reference 'refs/heads/main' not found" in str(headless):
            ref = "HEAD"
            parents = []
        else:
            raise  # pragma: no cover

    if not message.endswith("\n"):
        message += "\n"

    config = _config()
    author = pygit2.Signature(config["user.name"], config["user.email"])
    committer = pygit2.Signature(config["committer.name"], config["committer.email"])
    repo.create_commit(
        ref, author, committer, message, repo.index.write_tree(), parents
    )


class Commit(NamedTuple):
    """Commit metadata

    Attributes
    ----------
    hash : str
        The full commit hash
    message : str
        The commit message
    timestamp : dt.datetime
        The timestamp of the commit
    """

    hash: str
    message: str
    timestamp: dt.datetime


def log(repo_root: Path, n: int) -> list[Commit]:
    """Return metadata about the last `n` commits such as you'd get by running
    `git log -<num>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    n : int
        The number of commits to go back. A value less than zero will retrieve
        the *full* history

    Returns
    -------
    list of commit
        The requested commits, returned in reverse-chronological order

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)

    history: list[Commit] = []

    for i, commit_object in enumerate(
        repo.walk(repo[repo.head.target].id, pygit2.GIT_SORT_NONE)
    ):
        if i + 1 == n:
            break
        history.append(
            Commit(
                commit_object.id,
                commit_object.message,
                dt.datetime.fromtimestamp(commit_object.commit_time),
            )
        )

    return history


def ls_files(repo_root: Path) -> list[Path]:
    """List the files in the index, similar to the output you'd get from
    running `git ls-files`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo

    Returns
    -------
    list of Path
        The files being tracked in this repo

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    return [repo_root / file.path for file in repo.index]


def tag(repo_root: Path, tag_name: str, annotation: str | None) -> None:
    """Create a tag at the current HEAD, equivalent to running
    `git tag [-am <annotation>]`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    tag_name : str
        The name to give the tag
    annotation : str or None
        The annotation to give the tag. If None is provided, a lightweight tag
        will be created

    Raises
    ------
    ValueError
        If there is already a tag with the provided name
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)

    config = _config()
    tagger = pygit2.Signature(config["committer.name"], config["committer.email"])

    if annotation:
        if not annotation.endswith("\n"):
            annotation += "\n"

        repo.create_tag(
            tag_name,
            repo.head.target,
            pygit2.GIT_OBJ_COMMIT,
            tagger,
            annotation,
        )
    else:
        repo.create_reference(f"refs/tags/{tag_name}", repo.head.target)

    # PSA: pygit2.AlreadyExistsError subclasses ValueError


class Tag(NamedTuple):
    """Tag metadata

    Attributes
    ----------
    name : str
        The name of the tag
    annotation : str or None
        The tag's annotation. If None, then this is a lightweight tag
    """

    name: str
    annotation: str | None
    # TODO : capture tagger as well for filtering to just gsb tags


def get_tags(repo_root: Path, annotated_only: bool) -> list[Tag]:
    """List the repo's tags, similar to the output you'd get from
    running `git tag -n`, with the additional option of filtering out
    lightweight tags

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    annotated_only : bool
        Lightweight tags will be included if and only if this is `False`.

    Returns
    -------
    list of Tag
        The requested list of tags

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    # TODO: add ability to filter out non-gsb tags
    repo = _repo(repo_root)
    tags: list[Tag] = []
    for reference in repo.references.iterator(pygit2.GIT_REFERENCES_TAGS):
        tag_object = repo.revparse_single(reference.name)
        if tag_object.type == pygit2.GIT_OBJ_TAG:
            tags.append(Tag(tag_object.name, tag_object.message))
        if tag_object.type == pygit2.GIT_OBJ_COMMIT:
            if annotated_only:
                continue
            tags.append(Tag(reference.shorthand, None))
    return sorted(tags)
