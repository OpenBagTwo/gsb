"""Functionality for tracking and managing revision history"""
import datetime as dt
from pathlib import Path
from typing import TypedDict

from . import _git


class Revision(TypedDict):
    """Metadata on a GSB-managed version

    Parameters
    ----------
    identifier : str
        A unique identifier for the revision
    description : str
        A description of the version
    timestamp : dt.datetime
        The time at which the version was created
    """

    identifier: str
    description: str
    timestamp: dt.datetime


def get_history(
    repo_root: Path,
    tagged_only: bool = True,
    include_non_gsb: bool = False,
    limit: int = -1,
    since: dt.date = dt.datetime(1970, 1, 1),
) -> list[Revision]:
    """Retrieve a list of GSB-managed versions

    Parameters
    ----------
    repo_root : Path
        The directory where the repo should be created
    tagged_only : bool, optional
        By default, this method only returns tagged backups. To include
        all available revisions, pass in `tagged_only=False`.
    include_non_gsb : bool, optional
        By default, this method excludes any revisions created outside of `gsb`.
        To include all git commits and tags, pass in `include_non_gsb=True`.
    limit : int, optional
        By default, this method returns the entire history. To return only the
        last _n_ revisions, pass in `limit=n`.
    since : date or timestamp, optional
        By default, this method returns the entire history. To return only
        revisions made on or after a certain date, pass in `since=<start_date>`.

    Returns
    -------
    list of dict
        metadata on the requested revisions, sorted in reverse-chronological
        order
    """
    raise NotImplementedError
