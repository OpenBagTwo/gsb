"""Command-line interface"""
import datetime as dt
import functools
import logging
import sys
from pathlib import Path
from typing import Any, Callable

import click

from . import _version
from . import backup as backup_
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
    pass


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
@click.argument(
    "path_as_arg",
    type=Path,
    required=False,
    metavar="[SAVE_PATH]",
)
@_subcommand_init
def backup(repo_root: Path, path_as_arg: Path | None, tag: str | None):
    """Create a new backup."""
    backup_.create_backup(path_as_arg or repo_root, tag)


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
    repo_root: Path, track_args: tuple[str], track: tuple[str], ignore: tuple[str]
):
    """Start tracking a save."""
    onboard.create_repo(repo_root, *track_args, *track, ignore=ignore)


@click.option(
    "--include_non_gsb",
    "-g",
    is_flag=True,
    help="Include backups created directly with Git / outside of gsb.",
)
@click.option("--all", "-a", "all_", is_flag=True, help="Include non-tagged commits.")
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

    history_.get_history(path_as_arg or repo_root, **kwargs)


@click.argument(
    "revision",
    type=str,
    required=False,
)
@_subcommand_init
def rewind(repo_root: Path, revision: str | None):
    """Restore a backup to the specified REVISION."""
    if revision is None:
        revision = _prompt_for_revision(repo_root)
    try:
        rewind_.restore_backup(repo_root, revision)
    except ValueError as whats_that:
        LOGGER.error(whats_that)
        sys.exit(1)


def _prompt_for_revision(repo_root) -> str:
    """Select a revision from a prompt"""
    LOGGER.log(IMPORTANT, "Here is a list of recent backups:")
    revisions = history_.get_history(repo_root, limit=10)
    if len(revisions) == 0:
        LOGGER.info("No tagged revisions found. Trying untagged.")
        revisions = history_.get_history(
            repo_root,
            limit=10,
            tagged_only=False,
        )
    if len(revisions) == 0:
        LOGGER.warning("No gsb revisions found. Trying Git.")
        revisions = history_.get_history(
            repo_root,
            limit=10,
            tagged_only=False,
            include_non_gsb=True,
        )
    LOGGER.log(
        IMPORTANT,
        "Select one by number or revision (or [q]uit and"
        " call gsb history yourself to get more revisions).",
    )
    if len(revisions) == 0:
        LOGGER.error("No revisions found!")
        sys.exit(1)

    choice: str = click.prompt(
        "Select a revision", default="q", show_default=True, type=str
    ).lower()

    if choice.lower().strip() == "q":
        LOGGER.error("Aborting.")
        sys.exit(1)
    if choice.strip() in [str(i + 1) for i in range(len(revisions))]:
        return revisions[int(choice.strip()) - 1]["identifier"]
    return choice
