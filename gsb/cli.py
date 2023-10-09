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
from . import fastforward
from . import history as history_
from . import onboard
from . import rewind as rewind_
from .logging import IMPORTANT, CLIFormatter, verbosity_to_log_level

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
def backup(repo_root: Path, path_as_arg: Path | None, tag: str | None, combine: int):
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
            raise probably_not_enough_values  # pragma: no-cover

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

    backup_.create_backup(path_as_arg or repo_root, tag, parent=parent_hash)


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
    "--include_non_gsb",
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
    "--include_gsb_settings",
    is_flag=True,
    help="Also revert the GSB configuration files (including .gitignore)",
)
@click.argument(
    "revision",
    type=str,
    required=False,
)
@_subcommand_init
def rewind(repo_root: Path, revision: str | None, include_gsb_settings: bool):
    """Restore a backup to the specified REVISION."""
    if revision is None:
        revision = _prompt_for_a_recent_revision(repo_root)
    try:
        rewind_.restore_backup(repo_root, revision, not include_gsb_settings)
    except ValueError as whats_that:
        LOGGER.error(whats_that)
        sys.exit(1)


def _prompt_for_a_recent_revision(repo_root) -> str:
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


@click.argument(
    "revisions", type=str, required=False, nargs=-1, metavar="[REVISION]..."
)
@_subcommand_init
def delete(repo_root: Path, revisions: tuple[str, ...]):
    """Delete one or more backups."""
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
