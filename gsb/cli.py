"""Command-line interface"""
from pathlib import Path

import click

from . import _version
from . import backup as backup_


@click.group()
@click.help_option("--help", "-h")
@click.version_option(_version.get_versions()["version"], "--version", "-v", "-V")
def gsb():
    """CLI for managing incremental backups of your save states using Git!"""
    pass


@gsb.command()
@click.argument(
    "path_as_arg",
    type=Path,
    required=False,
    metavar="SAVE_PATH",
)
@click.option(
    "--path",
    type=Path,
    metavar="SAVE_PATH",
    help=(
        "Optionally specify the root directory containing your save data."
        " If no path is given, the current working directory will be used."
    ),
)
@click.option(
    "--tag",
    type=str,
    help='Specify a description for this backup and "tag" it for future reference.',
)
def backup(path_as_arg: Path | None, path: Path | None, tag: str | None):
    """Create a new backup"""
    if path_as_arg is not None and path is not None and path_as_arg != path:
        raise SyntaxError("Conflicting values given for SAVE_PATH")
    repo_root = path_as_arg or path or Path()
    backup_.create_backup(repo_root, tag)
