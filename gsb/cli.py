"""Command-line interface"""
import functools
from pathlib import Path
from typing import Callable

import click

from . import _version
from . import backup as backup_


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
        path_as_arg: Path | None, path: Path | None, *args, **kwargs
    ) -> Callable:
        if path_as_arg is not None and path is not None and path_as_arg != path:
            raise SyntaxError("Conflicting values given for SAVE_PATH")
        repo_root = path_as_arg or path or Path()
        return command(repo_root, *args, **kwargs)

    wrapped = click.argument(
        "path_as_arg",
        type=Path,
        required=False,
        metavar="SAVE_PATH",
    )(wrapped)
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
@_subcommand_init
def backup(repo_root: Path, tag: str | None):
    """Create a new backup"""

    backup_.create_backup(repo_root, tag)
