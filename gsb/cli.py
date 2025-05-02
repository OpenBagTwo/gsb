"""Command-line interface"""

import datetime as dt
import functools
import logging
import sys
from pathlib import Path
from typing import Any, Callable

import click

from . import _git, _version
from . import backup as backup_
from . import export as export_
from . import fastforward
from . import history as history_
from . import onboard
from . import rewind as rewind_
from .logging import IMPORTANT, CLIFormatter, verbosity_to_log_level
from .manifest import Manifest

LOGGER = logging.getLogger(__package__)


@click.group()
@click.help_option("--help", "-h")
@click.version_option(_version.get_versions()["version"], "--version", "-v", "-V")
def gsb():
    """CLI for managing incremental backups of your save states using Git!"""


def _subcommand_init(command: Callable) -> Callable:
    """Register a subcommand and add some standard CLI handling"""

    @functools.wraps(command)
    def wrapped(path: Path | None, verbose: int, quiet: int, *args, **kwargs) -> None:
        cli_handler = logging.StreamHandler()
        cli_handler.setFormatter(CLIFormatter())
        LOGGER.addHandler(cli_handler)

        log_level = verbosity_to_log_level(verbose - quiet)

        cli_handler.setLevel(log_level)

        # TODO: when we add log files, set this to minimum log level across all handlers
        LOGGER.setLevel(log_level)
        try:
            command((path or Path()).absolute(), *args, **kwargs)
        except (OSError, ValueError) as oh_no:
            LOGGER.error(oh_no)
            sys.exit(1)

    wrapped = click.option(
        "--path",
        type=Path,
        metavar="SAVE_PATH",
        help=(
            "Optionally specify the root directory containing your save data."
            " If no path is given, the current working directory will be used."
        ),
    )(wrapped)

    wrapped = click.option(
        "--verbose",
        "-v",
        count=True,
        help="Increase the amount of information that's printed.",
    )(wrapped)

    wrapped = click.option(
        "--quiet",
        "-q",
        count=True,
        help="Decrease the amount of information that's printed.",
    )(wrapped)
    return gsb.command()(wrapped)


@click.option(
    "--ignore-empty",
    "-i",
    is_flag=True,
    help=(
        "Do not return an error code if there's nothing to commit"
        " (this flag only applies for untagged backups)"
    ),
)
@click.option(
    "--tag",
    type=str,
    help='Specify a description for this backup and "tag" it for future reference.',
    metavar='"MESSAGE"',
)
@click.option(
    "--combine",
    "-c",
    count=True,
    help=(
        "Combine this backup and the last backup,"
        " or use -cc to combine ALL backups since the last tagged backup."
    ),
)
@click.argument(
    "path_as_arg",
    type=Path,
    required=False,
    metavar="[SAVE_PATH]",
)
@_subcommand_init
def backup(
    repo_root: Path,
    path_as_arg: Path | None,
    tag: str | None,
    combine: int,
    ignore_empty: bool,
):
    """Create a new backup."""
    parent_hash = None
    if combine == 1:
        try:
            combine_me, parent = history_.get_history(
                repo_root, tagged_only=False, include_non_gsb=True, limit=2
            )
        except ValueError as probably_not_enough_values:
            if "not enough values to unpack" in str(probably_not_enough_values):
                LOGGER.error("Cannot combine with the very first backup.")
                sys.exit(1)
            raise probably_not_enough_values  # pragma: no cover

        LOGGER.log(IMPORTANT, "Combining with %s", combine_me["identifier"])
        if combine_me["tagged"]:
            LOGGER.warning("Are you sure you want to overwrite a tagged backup?")
            history_.log_revision(combine_me, None)
            confirmed: bool = click.confirm(
                "",
                default=False,
                show_default=True,
            )
            if not confirmed:
                LOGGER.error("Aborting.")
                sys.exit(1)
            _git.delete_tag(repo_root, combine_me["identifier"])
        parent_hash = parent["identifier"]
    if combine > 1:
        try:
            last_tag = history_.get_history(repo_root, tagged_only=True, limit=1)[0]
        except IndexError:
            LOGGER.error("There are no previous tagged backups.")
            sys.exit(1)
        LOGGER.log(IMPORTANT, "Combining with the following backups:")
        combining = history_.show_history(
            repo_root,
            tagged_only=False,
            include_non_gsb=True,
            since_last_tagged_backup=True,
        )
        if not combining:
            LOGGER.log(IMPORTANT, "(no backups to combine)")
        parent_hash = last_tag["identifier"]

    try:
        backup_.create_backup(
            path_as_arg or repo_root,
            tag,
            parent=parent_hash,
        )
    except ValueError as nothing_to_commit:
        if ignore_empty:
            LOGGER.warning("Nothing to commit")
        else:
            raise nothing_to_commit


@click.option(
    "--ignore",
    type=str,
    required=False,
    multiple=True,
    help=(
        "Provide a glob pattern to ignore. Each ignore pattern"
        ' must be prefaced with the "--ignore" flag.'
    ),
)
@click.option(
    "--track",
    type=str,
    required=False,
    multiple=True,
    help=(
        "Provide a glob pattern to track (note: arguments without any flag will"
        " also be treated as track patterns)."
    ),
)
@click.argument(
    "track_args", type=str, required=False, nargs=-1, metavar="[TRACK_PATTERN]..."
)
@_subcommand_init
def init(
    repo_root: Path,
    track_args: tuple[str, ...],
    track: tuple[str, ...],
    ignore: tuple[str, ...],
):
    """Start tracking a save."""
    onboard.create_repo(repo_root, *track_args, *track, ignore=ignore)


@click.option(
    "--include-non-gsb",
    "-g",
    is_flag=True,
    help="Include backups created directly with Git / outside of gsb.",
)
@click.option("--all", "-a", "all_", is_flag=True, help="Include non-tagged backups.")
@click.option(
    "--since",
    type=click.DateTime(),
    required=False,
    help="Only show backups created after the specified date.",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    required=False,
    help="The maximum number of backups to return.",
)
@click.argument(
    "path_as_arg",
    type=Path,
    required=False,
    metavar="[SAVE_PATH]",
)
@_subcommand_init
def history(
    repo_root: Path,
    path_as_arg: Path | None,
    limit: int | None,
    since: dt.datetime | None,
    all_: bool,
    include_non_gsb: bool,
):
    """List the available backups, starting with the most recent."""

    kwargs: dict[str, Any] = {
        "tagged_only": not all_,
        "include_non_gsb": include_non_gsb,
    }
    if limit is not None:
        if limit <= 0:
            LOGGER.error("Limit must be a positive integer")
            sys.exit(1)
        kwargs["limit"] = limit
    if since is not None:
        kwargs["since"] = since

    history_.show_history(
        path_as_arg or repo_root, **kwargs, always_include_latest=True
    )


@click.option(
    "--include-gsb-settings",
    is_flag=True,
    help="Also revert the GSB configuration files (including .gitignore)",
)
@click.option(
    "--delete-original",
    is_flag=True,
    help="Delete the original backup from the history (incompatible with --hard)",
)
@click.option(
    "--hard",
    is_flag=True,
    help=(
        "Discard any changes (backed up or no)"
        " since the specified (default: latest) revision"
    ),
)
@click.argument(
    "revision",
    type=str,
    required=False,
)
@_subcommand_init
def rewind(
    repo_root: Path,
    revision: str | None,
    hard: bool,
    delete_original: bool,
    include_gsb_settings: bool,
):
    """Restore a backup to the specified REVISION."""
    if hard:
        if delete_original:
            LOGGER.error("--delete-original and --hard cannot be used together")
            sys.exit(1)
        if revision is None:
            revision = history_.get_history(
                repo_root, tagged_only=False, include_non_gsb=True, limit=1
            )[0]["identifier"]
        _enumerate_revisions_to_be_discarded(repo_root, revision)
    if revision is None:
        revision = _prompt_for_a_recent_revision(repo_root)
    try:
        rewind_.restore_backup(
            repo_root, revision, keep_gsb_files=not include_gsb_settings, hard=hard
        )
        if delete_original:
            fastforward.delete_backups(repo_root, revision)
    except ValueError as whats_that:
        LOGGER.error(whats_that)
        sys.exit(1)


def _prompt_for_a_recent_revision(repo_root: Path) -> str:
    """Select a recent revision from a prompt"""
    LOGGER.log(IMPORTANT, "Here is a list of recent backups:")
    revisions = history_.show_history(repo_root, limit=10)
    if len(revisions) == 0:
        LOGGER.info("No tagged revisions found. Trying untagged.")
        revisions = history_.show_history(
            repo_root,
            limit=10,
            tagged_only=False,
        )
    if len(revisions) == 0:
        LOGGER.warning("No GSB revisions found. Trying Git.")
        revisions = history_.show_history(
            repo_root,
            limit=10,
            tagged_only=False,
            include_non_gsb=True,
        )
    if len(revisions) == 0:
        LOGGER.error("No revisions found!")
        sys.exit(1)
    LOGGER.log(IMPORTANT, "\nMost recent backup:")
    most_recent_backup = history_.show_history(
        repo_root, limit=1, always_include_latest=True, numbering=0
    )[0]

    LOGGER.log(
        IMPORTANT,
        "\nSelect one by number or identifier (or [q]uit and"
        " call gsb history yourself to get more revisions).",
    )

    choice: str = click.prompt(
        "Select a revision", default="q", show_default=True, type=str
    ).lower()

    if choice.lower().strip() == "q":
        LOGGER.error("Aborting.")
        sys.exit(1)
    if choice.strip() == "0":
        return most_recent_backup["identifier"]
    if choice.strip() in [str(i + 1) for i in range(len(revisions))]:
        return revisions[int(choice.strip()) - 1]["identifier"]
    return choice


def _enumerate_revisions_to_be_discarded(repo_root: Path, restore_point: str) -> None:
    """List all the backups to be deleted by a hard restore to the restore-point,
    then ask the user for confirmation"""

    # figure out how far back this is in the history
    break_point = _git.show(repo_root, restore_point)
    if isinstance(break_point, _git.Tag):
        break_point = break_point.target
    limit = 0
    for revision in _git.log(repo_root):
        if revision == break_point:
            break
        limit += 1
    else:  # pragma: no cover
        LOGGER.error("Specified revision is not in the current history. Cannot rewind.")
        sys.exit(1)

    LOGGER.warning("The following backups will be deleted:")
    history_.show_history(
        repo_root, numbering=None, tagged_only=False, include_non_gsb=True, limit=limit
    )
    LOGGER.warning("\nalong with any unsaved changes.\n")

    confirmed: bool = click.confirm(
        "Are you sure you wish to continue?",
        default=False,
        show_default=True,
    )
    if not confirmed:
        LOGGER.error("Aborting.")
        sys.exit(1)


@click.argument(
    "revisions", type=str, required=False, nargs=-1, metavar="[REVISION]..."
)
@_subcommand_init
def delete(repo_root: Path, revisions: tuple[str, ...]):
    """Delete one or more backups by their specified REVISION."""
    if not revisions:
        revisions = _prompt_for_revisions_to_delete(repo_root)
    try:
        fastforward.delete_backups(repo_root, *revisions)
        LOGGER.log(
            IMPORTANT,
            'Deleted backups are now marked as "loose."'
            " To delete them immediately, run the command:"
            "\n  git gc --aggressive --prune=now",
        )
    except ValueError as whats_that:
        LOGGER.error(whats_that)
        sys.exit(1)


def _prompt_for_revisions_to_delete(repo_root: Path) -> tuple[str, ...]:
    """Offer a history of revisions to delete. Unlike similar prompts, this
    is a multiselect and requires the user to type in each entry (in order to guard
    against accidental deletions)."""
    LOGGER.log(IMPORTANT, "Here is a list of recent GSB-created backups:")
    revisions = history_.show_history(
        repo_root, tagged_only=False, since_last_tagged_backup=True, numbering=None
    )
    revisions.extend(history_.show_history(repo_root, limit=3, numbering=None))
    if len(revisions) == 0:
        LOGGER.warning("No GSB revisions found. Trying Git.")
        revisions = history_.show_history(
            repo_root, limit=10, tagged_only=False, include_non_gsb=True, numbering=None
        )
    LOGGER.log(
        IMPORTANT,
        "\nSelect a backup to delete by identifier, or multiple separated by commas."
        "\nAlternatively, [q]uit and call gsb history yourself to get more revisions.",
    )
    if len(revisions) == 0:
        LOGGER.error("No revisions found!")
        sys.exit(1)

    choices: str = click.prompt(
        "Select a revision or revisions", default="q", show_default=True, type=str
    ).lower()

    if choices.lower().strip() == "q":
        LOGGER.error("Aborting.")
        sys.exit(1)
    return tuple(choice.strip() for choice in choices.strip().split(","))


@click.option(
    "-J",
    "xz_flag",
    is_flag=True,
    flag_value="tar.xz",
    help="Export as a .tar.xz archive.",
)
@click.option(
    "-j",
    "bz2_flag",
    is_flag=True,
    flag_value="tar.bz2",
    help="Export as a .tar.bz2 archive.",
)
@click.option(
    "-z",
    "gz_flag",
    is_flag=True,
    flag_value="tar.gz",
    help="Export as a .tar.gz archive.",
)
@click.option(
    "-t",
    "tar_flag",
    is_flag=True,
    flag_value="tar",
    help="Export as an uncompressed .tar archive.",
)
@click.option(
    "-p",
    "zip_flag",
    is_flag=True,
    flag_value="zip",
    help="Export as a .zip archive.",
)
@click.option(
    "--format",
    "archive_format",
    type=str,
    required=False,
    help=(
        "Format for the archived backup. If not specified,"
        " an appropriate one will be chosen based on your OS."
    ),
    metavar="FORMAT",
)
@click.option(
    "--output",
    "-o",
    type=Path,
    required=False,
    help=(
        "Explicitly specify a filename for the archived backup."
        " The format of the archive will be inferred from the extension"
        " unless a format flag is provided."
    ),
    metavar="FILENAME",
)
@click.argument(
    "revision",
    type=str,
    required=False,
)
@_subcommand_init
def export(
    repo_root: Path,
    revision: str | None,
    output: Path | None,
    **format_flags,
):
    """Create a stand-alone archive of the specified REVISION."""
    specified_formats: list[str] = [value for value in format_flags.values() if value]

    if len(specified_formats) > 1:
        LOGGER.error("Conflicting values given for archive format")
        sys.exit(1)

    if revision is None:
        revision = _prompt_for_a_recent_revision(repo_root)

    if len(specified_formats) == 1:
        archive_format = specified_formats[0]
        if archive_format.startswith("."):
            archive_format = archive_format[1:]
        if output is None:
            output = Path(
                export_.generate_archive_name(
                    Manifest.of(repo_root).name, revision, extension=archive_format
                )
            )
        else:
            output = output.parent / (output.name + f".{archive_format}")

    try:
        export_.export_backup(repo_root, revision, output)
    except ValueError as whats_that:
        LOGGER.error(whats_that)
        sys.exit(1)


@click.argument(
    "pytest_args",
    nargs=-1,
)
@gsb.command(context_settings={"ignore_unknown_options": True})
def test(pytest_args: tuple[str, ...]):  # pragma: no cover
    """Run the GSB test suite to ensure that it is running correctly on your system.
    Requires you to have installed GSB with the test extra
    (_i.e._ `pipx install gsb[test]`)."""
    import pytest

    pytest.main(["--pyargs", "gsb.test", *pytest_args])
