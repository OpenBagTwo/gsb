"""Functionality for creating standalone backups"""
import os
from pathlib import Path

import pathvalidate

from . import _git
from .manifest import Manifest


def generate_archive_name(
    repo_name: str, revision: str, extension: str | None = None
) -> str:
    """Programmatically generate a name for an archived backup

    Parameters
    ----------
    repo_name : str
        The alias assigned to the GSB-managed repo
    revision : str
        The commit hash or tag name of the backup that's being archived
    extension : str, optional
        The file extension for the archive (thus specifying the archive's format).
        If None is provided, an appropriate one will be chosen based on the
        operating system.

    Returns
    -------
    str
        A (hopefully) descriptive archive filename, including a format-specifying
        extension

    Notes
    -----
    The default choice of extension (and thus format) is:

    - zip for Windows
    - tar.gz for all other systems
    """
    if extension is None:
        extension = "zip" if os.name == "nt" else "tar.gz"
    return pathvalidate.sanitize_filename(f"{repo_name}_{revision}.{extension}")


def export_backup(
    repo_root: Path,
    revision: str,
    archive_path: Path | None = None,
) -> None:
    """Export a backup to a stand-alone archive

    Parameters
    ----------
    repo_root : Path
        The directory containing the GSB-managed repo
    revision : str
        The commit hash or tag name of the backup to archive
    archive_path : Path, optional
        The full path to save the archive, including the filename and the
        extension. If None is provided, one will be automatically generated
        in the current working directory based on the repo's name and the
        specified revision.

    Raises
    ------
    OSError
        If the specified repo does not exist or is not a GSB-managed repo
    ValueError
        If the specified revision does not exist or if the given `archive_path`
        does not have a valid extension
    NotImplementedError
        If the compression schema implied by the `archive_path`'s extension is not
        supported
    """
    if archive_path is None:
        archive_path = Path(
            generate_archive_name(Manifest.of(repo_root).name, revision)
        )

    _git.archive(repo_root, archive_path, revision)
