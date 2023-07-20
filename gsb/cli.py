"""Command-line interface"""
import functools
import logging
from pathlib import Path
from typing import Callable

import click

from . import _version
from . import backup as backup_
from . import onboard
from .logging import CLIFormatter, verbosity_to_log_level

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
    def wrapped(
        path: Path | None, verbose: int, quiet: int, *args, **kwargs
    ) -> Callable:
        cli_handler = logging.StreamHandler()
        cli_handler.setFormatter(CLIFormatter())
        LOGGER.addHandler(cli_handler)

        log_level = verbosity_to_log_level(verbose - quiet)

        cli_handler.setLevel(log_level)

        # TODO: when we add log files, set this to minimum log level across all handlers
        LOGGER.setLevel(log_level)

        return command((path or Path()).absolute(), *args, **kwargs)

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
    """Create a new backup"""
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
    """Start tracking a save"""
    onboard.create_repo(repo_root, *track_args, *track, ignore=ignore)
