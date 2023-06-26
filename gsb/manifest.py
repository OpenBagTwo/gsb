"""Configuration definition for an individual GSB-managed save"""
from pathlib import Path
from typing import NamedTuple, Self

MANIFEST_NAME = ".gsb_manifest"


class Manifest(NamedTuple):
    """Save-specific configuration

    Attributes
    ----------
    root : Path
        The directory containing the save / repo
    patterns : tuple of str
        The glob match-patterns that determine which files get tracked
    """

    root: Path
    patterns: tuple[str, ...]

    @classmethod
    def read(cls, file_path: Path) -> Self:
        """Read a manifest from file

        Parameters
        ----------
        file_path : Path
            The location of the manifest file

        Returns
        -------
        Manifest
            the parsed manifest

        Raises
        ------
        ValueError
            If the configuration cannot be parsed
        OSError
            If the file does not exist or cannot otherwise be read
        """
        raise NotImplementedError

    def write(self) -> None:
        """Write the manifest to file, overwriting any existing configuration

        Returns
        -------
        None

        Notes
        -----
        The location and name of this file is controlled by the `root` attribute
        and the `MANIFEST_NAME` constant, respectively, and cannot be overridden

        Raises
        ------
        OSError
            If the destination folder (`root`) does not exist or cannot be
            written to
        """
        raise NotImplementedError
