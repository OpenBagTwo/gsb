"""Functionality for onboarding a new save state"""
import datetime as dt
from pathlib import Path
from typing import Iterable

from . import _git
from .manifest import MANIFEST_NAME, Manifest

DEFAULT_IGNORE_LIST: tuple[str, ...] = ()


# TODO: these two are probably going to get refactored somewhere else
REQUIRED_FILES: tuple[Path, ...] = (Path(".gitignore"), Path(MANIFEST_NAME))


def _generate_tag_name() -> str:
    """Generate a new calver-ish tag name

    Returns
    -------
    str
        A tag name that should hopefully be distinctly gsb and distinct
        from any tags a user would manually create

    Notes
    -----
    When unit testing, this method will need to be monkeypatched to provide
    even greater granularity... unless you want to use `time.sleep(1)` between
    each tag :O
    """
    return dt.datetime.now().strftime("gsb%Y.%m.%d+%H%M%S")


def create_repo(
    repo_root: Path, *patterns: str, ignore: Iterable[str] | None = None
) -> Manifest:
    """Create a new `gsb`-managed git repo in the specified location

    Parameters
    ----------
    repo_root : Path
        The directory where the repo should be created
    patterns : str
        List of glob-patterns to match, specifying what in the working directory
        should be archived. If none are provided, then it will be assumed that
        the intent is to back up the *entire* folder and all its contents.
    ignore : list of str, optional
        List of glob-patterns to *ignore*. If None are specified, then nothing
        will be ignored.

    Returns
    -------
    Manifest
        The static configuration for that repo

    Raises
    ------
    FileExistsError
        If there is already a `gsb` repo in that location
    OSError
        If `repo_root` does not exist, is not a directory or cannot be accessed
    """
    if (repo_root / MANIFEST_NAME).exists():
        raise FileExistsError(f"{repo_root} already contains a GSB-managed repo")
    if not patterns:
        patterns = (".",)
    if "." not in patterns:
        patterns = tuple(set(patterns))

    _git.init(repo_root)

    _update_gitignore(repo_root, ignore or ())

    # enforce round-trip
    Manifest(repo_root, tuple(patterns)).write()
    manifest = Manifest.of(repo_root)

    _git.add(repo_root, patterns)
    _git.force_add(repo_root, REQUIRED_FILES)
    _git.commit(repo_root, "Started tracking with gsb")
    _git.tag(repo_root, _generate_tag_name(), "Start of gsb tracking")

    return manifest


def _update_gitignore(repo_root: Path, patterns: Iterable[str]) -> None:
    """Create or append to the ".gitignore" file in the specified repo

    Parameters
    ----------
    repo_root : Path
        The directory where the repo should be created
    patterns
        List of glob-patterns to ignore
    """
    with open(repo_root / ".gitignore", "a+", encoding="UTF-8") as gitignore:
        gitignore.seek(0)
        existing_lines: list[str] = [line.strip() for line in gitignore.readlines()]
        if existing_lines and "# gsb" not in existing_lines:
            gitignore.write("\n# gsb\n")
        new_lines: list[str] = sorted(
            [
                pattern
                for pattern in {*DEFAULT_IGNORE_LIST, *patterns}
                if pattern not in existing_lines
            ]
        )
        gitignore.write("\n".join(new_lines) + "\n")
