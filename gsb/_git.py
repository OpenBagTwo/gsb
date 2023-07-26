"""Abstraction around the git library interface (to allow for easier backend swaps"""
import datetime as dt
import getpass
import logging
import re
import socket
from pathlib import Path
from typing import Generator, Iterable, NamedTuple, Self

import pygit2

LOGGER = logging.getLogger(__name__)


def init(repo_root: Path) -> pygit2.Repository:
    """Initialize (or re-initialize) a git repo, equivalent to running
    `git init`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo

    Returns
    -------
    repo
        The initialized git repository

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    LOGGER.debug("git init %s", repo_root)
    return _repo(repo_root, new=True)


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
        If `repo_root` does not exist or the repo is not a valid repository
        and `new=False`
    OSError
        If `repo_root` cannot otherwise be accessed
    """
    repo_root = repo_root.expanduser().resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"{repo_root} does not exist")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"{repo_root} is not a directory")
    if new:
        return pygit2.init_repository(repo_root, initial_head="gsb")
    try:
        return pygit2.Repository(repo_root)
    except pygit2.GitError as maybe_no_git:
        if "repository not found" in str(maybe_no_git).lower():
            raise FileNotFoundError(maybe_no_git) from maybe_no_git
        raise  # pragma: no cover


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
    LOGGER.debug("git config --global --list")
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


def add(repo_root: Path, patterns: Iterable[str]) -> pygit2.Index:
    """Add files matching the given pattern to the repo, equivalent to running
    `git add <pattern>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    patterns : list of str
        The glob patterns to match

    Returns
    -------
    index
        The updated git index

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    patterns = list(patterns)
    repo.index.add_all(patterns)
    for pattern in patterns:
        LOGGER.debug("git add %s", pattern)
    repo.index.write()
    return repo.index


def force_add(repo_root: Path, files: Iterable[Path]) -> pygit2.Index:
    """Forcibly add specific files, overriding .gitignore, equivalent to running
    `git add <file> --force`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    files : list of paths
        The file paths to add, relative to the repo root

    Returns
    -------
    index
        The updated git index

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
            LOGGER.debug("git add --force %s", path)
        except OSError as maybe_file_not_found:  # pragma: no cover
            if "No such file or directory" in str(maybe_file_not_found):
                raise FileNotFoundError(maybe_file_not_found) from maybe_file_not_found
            raise  # pragma: no cover
        except pygit2.GitError as maybe_directory:  # pragma: no cover
            if "is a directory" in str(maybe_directory):
                raise IsADirectoryError(maybe_directory) from maybe_directory
    repo.index.write()
    return repo.index


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
    gsb : bool
        True if and only if the tag was created by `gsb`
    """

    hash: str
    message: str
    timestamp: dt.datetime
    gsb: bool

    @classmethod
    def from_pygit2(cls, commit_object: pygit2.Object) -> Self:
        """Resolve from a pygit2 object"""
        try:
            gsb = commit_object.committer.name == "gsb"
        except AttributeError:  # pragma: no cover
            gsb = False
        return cls(
            str(commit_object.id),
            commit_object.message,
            dt.datetime.fromtimestamp(commit_object.commit_time),
            gsb,
        )


def commit(
    repo_root: Path, message: str, _committer: tuple[str, str] | None = None
) -> Commit:
    """Commit staged changes, equivalent to running `git commit -m <message>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    message : str
        The commit message
    _committer : (str, str) tuple
        By default this method uses "gsb" as the committer. This should not
        be overridden outside of testing, but to do so, pass in both the
        username and email address.

    Returns
    -------
    commit
        The generated commit object

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    ValueError
        If the commit is empty ("nothing to do")
    """
    repo = _repo(repo_root)
    try:
        ref = repo.head.name
        parents = [repo.head.target]
    except pygit2.GitError as headless:
        if "reference 'refs/heads/gsb' not found" in str(headless):
            ref = "HEAD"
            parents = []
        else:
            raise  # pragma: no cover
    if not repo.status(untracked_files="no"):
        raise ValueError("Nothing to commit")

    if not message.endswith("\n"):
        message += "\n"

    config = _config()
    author = pygit2.Signature(config["user.name"], config["user.email"])
    if _committer is None:
        committer = pygit2.Signature(
            config["committer.name"], config["committer.email"]
        )
    else:
        committer = pygit2.Signature(*_committer)
    commit_id = repo.create_commit(
        ref, author, committer, message, repo.index.write_tree(), parents
    )
    LOGGER.debug("git commit -m %s", message)
    return Commit.from_pygit2(repo[commit_id])


def log(repo_root: Path) -> Generator[Commit, None, None]:
    """Return metadata about commits such as you'd get by running `git log`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo

    Returns
    -------
    iterable of commit
        The requested commits, returned lazily, in reverse-chronological order

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)

    LOGGER.debug("git log")
    try:
        for commit_object in repo.walk(repo[repo.head.target].id, pygit2.GIT_SORT_NONE):
            yield Commit.from_pygit2(commit_object)
    except pygit2.GitError as maybe_empty_history:
        if re.search("reference (.*) not found", str(maybe_empty_history)):
            # this is what pygit2 throws when there's no commits
            return
        raise  # pragma: no cover


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
    LOGGER.debug("git ls-files")
    return [repo_root / file.path for file in repo.index]


class Tag(NamedTuple):
    """Tag metadata

    Attributes
    ----------
    name : str
        The name of the tag
    annotation : str or None
        The tag's annotation. If None, then this is a lightweight tag
    target : Commit
        The commit the tag is targeting
    gsb : bool or None
        True if the tagger was  `gsb`, False if it was created by
        someone / something else and None if it's a lightweight tag (which
        doesn't have a tagger)
    """

    name: str
    annotation: str | None
    target: Commit
    gsb: bool | None

    @classmethod
    def from_repo_reference(
        cls, reference: pygit2.Reference | str, repo: pygit2.Repository
    ) -> Self:
        """Parse the reference and resolve from the pygit2 object"""
        if isinstance(reference, str):
            tag_object = repo.revparse_single(reference)
        else:
            tag_object = repo.revparse_single(reference.name)
            reference = reference.shorthand

        if tag_object.type == pygit2.GIT_OBJ_TAG:
            try:
                gsb = tag_object.tagger.name == "gsb"
            except AttributeError:  # pragma: no cover
                gsb = False
            return cls(
                tag_object.name,
                tag_object.message,
                Commit.from_pygit2(repo[tag_object.target]),
                gsb,
            )
        if tag_object.type == pygit2.GIT_OBJ_COMMIT:
            return cls(reference, None, Commit.from_pygit2(tag_object), False)
        raise TypeError(  # pragma: no cover
            f"Don't know how to parse reference of type: {tag_object.type}"
        )


def tag(
    repo_root: Path,
    tag_name: str,
    annotation: str | None,
    _tagger: tuple[str, str] | None = None,
) -> Tag:
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
    _tagger : (str, str) tuple
        By default this method uses "gsb" as the tagger. This should not
        be overridden outside of testing, but to do so, pass in both the
        username and email address.

    Returns
    -------
    tag
        The generated tag object

    Raises
    ------
    ValueError
        If there is already a tag with the provided name
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)

    config = _config()
    if _tagger is None:
        tagger = pygit2.Signature(config["committer.name"], config["committer.email"])
    else:
        tagger = pygit2.Signature(*_tagger)

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
        LOGGER.debug("git tag %s -am %s", tag_name, annotation)
    else:
        repo.create_reference(f"refs/tags/{tag_name}", repo.head.target)
        LOGGER.debug("git tag %s", tag_name)

    return Tag.from_repo_reference(tag_name, repo)

    # PSA: pygit2.AlreadyExistsError subclasses ValueError


def get_tags(repo_root: Path, annotated_only: bool) -> list[Tag]:
    """List the repo's tags, similar to the output you'd get from
    running `git tag`, with the additional option of filtering out
    lightweight tags

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    annotated_only : bool
        Lightweight tags will be included if and only if this is `False`

    Returns
    -------
    list of Tag
        The requested list of tags, sorted in lexical order

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    tags: list[Tag] = []
    for reference in repo.references.iterator(pygit2.GIT_REFERENCES_TAGS):
        parsed_tag = Tag.from_repo_reference(reference, repo)
        if parsed_tag.annotation or not annotated_only:
            tags.append(parsed_tag)
    LOGGER.debug("git tag")
    return sorted(tags)


def show(repo_root: Path, reference: str) -> Commit | Tag:
    """Get information about a specified revision, similar to the output you'd
    get from running `git show <commit-hash-or-tag-name>`.

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    reference : str
        A unique descriptor of the tag or commit

    Returns
    -------
    Commit or Tag
        The requested tag or commit

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    ValueError
        If the specified revision does not exist
    """
    repo = _repo(repo_root)
    try:
        revision = repo.revparse_single(reference)
        LOGGER.debug("git show %s", reference)
    except KeyError as no_rev:
        raise ValueError(
            f"Could not find a revision named {repr(reference)}"
        ) from no_rev
    if revision.type == pygit2.GIT_OBJ_TAG:
        return Tag.from_repo_reference(str(revision.id), repo)
    if revision.type == pygit2.GIT_OBJ_COMMIT:
        return Commit.from_pygit2(revision)
    raise TypeError(  # pragma: no cover
        f"Object of type {revision.type} is not a valid revision"
    )


def reset(repo_root: Path, reference: str, hard: bool) -> None:
    """Reset the repo to the specified revision, equivalent to running
    `git reset [--hard/--soft] <revision>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    reference : str
        A unique descriptor of the tag or commit
    hard : bool
        If True, perform a hard reset. If False, perform a soft reset.

    Returns
    -------
    None

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    ValueError
        If the specified revision does not exist
    """
    repo = _repo(repo_root)
    try:
        reference = repo.revparse_single(reference).id
    except KeyError as no_rev:
        raise ValueError(
            f"Could not find a revision named {repr(reference)}"
        ) from no_rev

    LOGGER.debug(f"git reset --{'hard' if hard else 'soft'} %s", reference)
    repo.reset(reference, pygit2.GIT_RESET_HARD if hard else pygit2.GIT_RESET_SOFT)
