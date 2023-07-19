"""Command-line interface"""
import functools
from pathlib import Path
from typing import Callable

import click

from . import _version
from . import backup as backup_
from . import onboard


@click.group()
@click.help_option("--help", "-h")
@click.version_option(_version.get_versions()["version"], "--version", "-v", "-V")
def gsb():
    """CLI for managing incremental backups of your save states using Git!"""
    pass


def _subcommand_init(command: Callable) -> Callable:
    """Register a subcommand and add some standard CLI handling"""

    @functools.wraps(command)
    def wrapped(path: Path | None, *args, **kwargs) -> Callable:
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

    return gsb.command()(wrapped)


@click.option(
    "--tag",
    type=str,
    help='Specify a description for this backup and "tag" it for future reference.',
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
