"""Abstraction around the git library interface (to allow for easier backend swaps"""
import datetime as dt
import getpass
import logging
import re
import socket
from pathlib import Path
from typing import Any, Generator, Iterable, NamedTuple, Self

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
    return _repo(repo_root, new=True)


def _repo(
    repo_root: Path, new: bool = False, initial_branch: str = "gsb"
) -> pygit2.Repository:
    """Load a git repository from the specified location

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    new : bool, optional
        By default, this method loads existing repositories. To initialize a new
        repo, pass in `new=True`
    initial_branch : str, optional
        By default, if a new repo is to be created, it will be given the initial
        branch name "gsb." To override this behavior (say, for testing) provide
        a different value to this argument.

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
        LOGGER.debug(
            "git init %s --initial-branch=%s", repr(str(repo_root)), initial_branch
        )
        return pygit2.init_repository(repo_root, initial_head=initial_branch)
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
    LOGGER.debug(
        "git add %s",
        " ".join([repr(pattern) for pattern in patterns]),
    )
    repo.index.add_all(patterns)
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
            LOGGER.debug("git add --force %s", repr(str(path)))
            repo.index.add(path)
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
    repo_root: Path,
    message: str,
    timestamp: dt.datetime | None = None,
    _committer: tuple[str, str] | None = None,
) -> Commit:
    """Commit staged changes, equivalent to running `git commit -m <message>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    message : str
        The commit message
    timestamp : dt.datetime, optional
        By default, commits are created using the current timestamp. Use this
        argument to provide a custom timestamp (as you would when calling
        `git commit --date <timestamp>`)
    _committer : (str, str) tuple, optional
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
        if re.search(r"reference 'refs/heads/(.*)' not found", str(headless)):
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
    signature_kwargs: dict[str, Any] = {}
    if timestamp is not None:
        signature_kwargs = {"time": int(timestamp.timestamp())}
    if _committer is None:
        committer = pygit2.Signature(
            config["committer.name"], config["committer.email"], **signature_kwargs
        )
    else:
        committer = pygit2.Signature(*_committer, **signature_kwargs)

    LOGGER.debug("git commit -m %s", repr(message))
    commit_id = repo.create_commit(
        ref, author, committer, message, repo.index.write_tree(), parents
    )
    return Commit.from_pygit2(repo[commit_id])


def log(
    repo_root: Path, starting_point: str | None = None
) -> Generator[Commit, None, None]:
    """Return metadata about commits such as you'd get by running `git log`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    starting_point : str, optional
        The default behavior is to walk backwards from the current repo HEAD.
        To specify a different starting point, provide an identifier for this
        variable.

    Returns
    -------
    iterable of commit
        The requested commits, returned lazily, in reverse-chronological order

    Raises
    ------
    ValueError
        If `starting_point` is provided and can't be resolved
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    try:
        if starting_point is not None:
            LOGGER.debug("git log %s", starting_point)
            head = _resolve_reference(starting_point, repo).id
        else:
            LOGGER.debug("git log")
            head = repo[repo.head.target].id
        for commit_object in repo.walk(head, pygit2.GIT_SORT_NONE):
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
    target: str | None = None,
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
    target : str, optional
        The commit to assign the tag. If None is given, the current HEAD will
        be used.
    _tagger : (str, str) tuple, optional
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
        If there is already a tag with the provided name, or if `target` is
        provided and can't be resolved
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)

    config = _config()
    if _tagger is None:
        tagger = pygit2.Signature(
            config["committer.name"],
            config["committer.email"],
        )
    else:
        tagger = pygit2.Signature(*_tagger)

    reference = _resolve_reference(target, repo).id if target else repo.head.target
    ref_short = str(reference)[:8] if target else "HEAD"

    if annotation:
        if not annotation.endswith("\n"):
            annotation += "\n"

        LOGGER.debug("git tag %s -am %s %s", tag_name, repr(annotation), ref_short)
        repo.create_tag(
            tag_name,
            reference,
            pygit2.GIT_OBJ_COMMIT,
            tagger,
            annotation,
        )
    else:
        LOGGER.debug("git tag %s %s", tag_name, ref_short)
        repo.create_reference(f"refs/tags/{tag_name}", reference)

    return Tag.from_repo_reference(tag_name, repo)

    # PSA: pygit2.AlreadyExistsError subclasses ValueError


def delete_tag(repo_root: Path, tag_name: str) -> None:
    """Delete a tag, equivalent to running `git tag -d <tag_name>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    tag_name : str
        The name to the tag to delete

    Raises
    ------
    ValueError
        If there is no tag with the provided name
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    repo = _repo(repo_root)
    try:
        LOGGER.debug("git tag -d %s", tag_name)
        repo.references[f"refs/tags/{tag_name}"].delete()
    except KeyError as tag_not_found:
        raise ValueError(f"No such tag: {tag_name}") from tag_not_found


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
    LOGGER.debug("git tag")
    for reference in repo.references.iterator(pygit2.GIT_REFERENCES_TAGS):
        parsed_tag = Tag.from_repo_reference(reference, repo)
        if parsed_tag.annotation or not annotated_only:
            tags.append(parsed_tag)
    return sorted(tags)


def _resolve_reference(reference: str, repo: pygit2.Repository) -> pygit2.Object:
    """Attempt to resolve a reference

    Parameters
    ----------
    reference : str
        The reference to resolve
    repo : Repository
        The git repository

    Returns
    -------
    pygit2.Object
        The resolved reference

    Raises
    ------
    ValueError
        If the specified revision does not exist
    """
    try:
        LOGGER.debug("git show %s", reference)
        return repo.revparse_single(reference)
    except KeyError as no_rev:
        raise ValueError(
            f"Could not find a revision named {repr(reference)}"
        ) from no_rev


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
    revision = _resolve_reference(reference, repo)
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

    # make sure revision exists
    reference = _resolve_reference(reference, repo).id

    LOGGER.debug(f"git reset --{'hard' if hard else 'soft'} %s", reference)
    repo.reset(reference, pygit2.GIT_RESET_HARD if hard else pygit2.GIT_RESET_SOFT)


def checkout_files(repo_root: Path, reference: str, paths: Iterable[Path]) -> None:
    """Check out the versions of the specified files that existed at the specified
    revision, equivalent to running
    `git reset <revision> -- <paths...> && git checkout <revision> -- <paths...>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    reference : str
        A unique descriptor of the tag or commit
    paths : list of Paths
        The files to reset

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

    revision = _resolve_reference(reference, repo)
    if isinstance(revision, pygit2.Tag):
        return checkout_files(repo_root, str(revision.target), paths)

    paths = list(paths)

    for path in paths:
        LOGGER.debug("git reset %s -- %s", reference, repr(str(path)))
        try:
            repo.index.remove(path)
        except OSError:
            pass  # possible that the file no longer exists
        try:
            past_file = revision.tree[path]
            repo.index.add(pygit2.IndexEntry(path, past_file.id, past_file.filemode))
        except KeyError:
            pass  # possible that the file doesn't exist at the time of the revision

    repo.index.write()
    LOGGER.debug(
        "git checkout %s -- %s",
        reference,
        " ".join((repr(str(path)) for path in paths)),
    )
    repo.checkout(strategy=pygit2.GIT_CHECKOUT_FORCE, paths=paths)
    return None


def checkout_branch(repo_root: Path, branch_name: str, target: str | None) -> None:
    """Check out a branch, either new or existing, equivalent to calling
    `git checkout [-b] <branch_name> [<target>]`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    branch_name : str
        The name for the branch
    target : str or None
        When a reference is provided, this method will attempt to create a new
        branch at that reference point. When None is provided, this method will
        attempt to check out an existing branch at that branch's head.

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    ValueError
        If the specified `target` does not exist, if the `branch_name` is taken
        (when `target` is specified) or if the `branch_name` _does not_ exist
        (when `target=None`)
    """
    repo = _repo(repo_root)
    if target is not None:
        LOGGER.debug("git checkout -b %s %s", branch_name, target)
        reference = _resolve_reference(target, repo)
        if isinstance(reference, pygit2.Tag):
            reference = _resolve_reference(str(reference.target), repo)
        repo.branches.local.create(branch_name, reference)
    try:
        LOGGER.debug("git checkout %s", branch_name)
        repo.checkout(repo.branches.local[branch_name])
    except KeyError as no_such_branch:
        raise ValueError(no_such_branch)


def delete_branch(repo_root: Path, branch_name: str) -> None:
    """Delete a branch, equivalent to running `git branch -D <branch_name>`

    Parameters
    ----------
    repo_root : Path
        The root directory of the git repo
    branch_name : str
        The name of the branch

    Raises
    ------
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    ValueError
        If the specified branch does not exist or if the specified branch is
        currently checked out
    """
    repo = _repo(repo_root)
    try:
        LOGGER.debug("git branch -D %s", branch_name)
        repo.branches.local.delete(branch_name)
    except KeyError as no_such_branch:
        raise ValueError(no_such_branch)
