"""Configuration definition for an individual GSB-managed save"""
import datetime as dt
import json
import logging
import tomllib
from pathlib import Path
from typing import Any, NamedTuple, Self, TypeAlias

from ._version import get_versions

LOGGER = logging.getLogger(__name__)

MANIFEST_NAME = ".gsb_manifest"

_ManifestDict: TypeAlias = dict[str, str | tuple[str, ...]]


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
    def of(cls, repo_root: Path) -> Self:
        """Read the manifest of the specified GSB repo

        Parameters
        ----------
        repo_root : Path
            The root directory of the gsb-managed repo

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
        LOGGER.debug("Loading %s from %s", MANIFEST_NAME, repo_root)
        as_dict: dict[str, Any] = {"root": repo_root}
        contents: _ManifestDict = tomllib.loads((repo_root / MANIFEST_NAME).read_text())
        for key, value in contents.items():
            if key in Manifest._fields:
                if isinstance(value, list):
                    value = tuple(value)
                as_dict[key] = value
        return cls(**as_dict)

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
        as_dict = {
            "generated_by_gsb": get_versions()["version"],
            "last_modified": dt.datetime.now().isoformat(sep=" "),
        }
        for attribute, value in self._asdict().items():  # pylint: disable=no-member
            #                  see: https://github.com/pylint-dev/pylint/issues/7891
            if attribute == "root":
                continue
            as_dict[attribute] = value

        as_toml = _to_toml(as_dict)

        LOGGER.debug("Writing %s to %s", MANIFEST_NAME, self.root)
        (self.root / MANIFEST_NAME).write_text(as_toml)


def _to_toml(manifest: _ManifestDict) -> str:
    """While Python 3.11 added native support for *parsing* TOML configurations,
    it didn't include an API for *writing* them (this was an intentional part
    of the PEP:
    https://peps.python.org/pep-0680/#including-an-api-for-writing-toml).

    Because the Manifest class is so simple, I'm rolling my own writer rather
    than adding a dependency on a third-party library. That being said, I'm
    abstracting that writer out in case I change my mind later. :D

    Parameters
    ----------
    manifest : dict
        A dict version of the manifest containing the entries that should be
        written to file

    Returns
    -------
    str
        The manifest serialized as a TOML-compatible str

    Notes
    -----
    This doesn't take an actual Manifest as a parameter so we can choose to
    omit some attributes (`root`) and add others (versioning metadata)
    """
    dumped = ""
    for key, value in manifest.items():
        dumped += f"{key} = "
        if isinstance(value, str):
            # it's honestly shocking how often I rely on json.dump for str escaping
            dumped += f"{json.dumps(value)}\n"
        else:
            dumped += "["
            for entry in sorted(set(value)):
                dumped += f"\n    {json.dumps(entry)},"
            dumped += "\n]\n"
    return dumped
