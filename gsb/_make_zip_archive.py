"""ZIP-compatible `repo.write_archive`, stand-alone for easier upstream sharing.
As it is adapted directly from pygit2, this module is licensed under the
GNU Public License v2."""
import datetime as dt
import zipfile
from time import time

from pygit2 import GIT_FILEMODE_LINK, Commit, Index, Oid, Repository, Tree


def write_zip_archive(
    repo: Repository,
    treeish,
    archive: zipfile.ZipFile,
    timestamp: int | None = None,
    prefix: str = "",
) -> None:
    """Implementation of `repo.write_archive` that supports ZIP. Writes treeish
    into an archive.

    If no timestamp is provided and 'treeish' is a commit, its committer
    timestamp will be used. Otherwise the current time will be used.

    All path names in the archive are added to 'prefix', which defaults to
    an empty string.

    Parameters
    ----------
    repo: Repository
        The git repository
    treeish
        The treeish to write
    archive : zipfile.ZipFile
        An archive from the 'zipfile' module.
    timestamp : int, optional
        (Epoch) timestamp to use for the files in the archive.
    prefix : str, optional
        Extra prefix to add to the path names in the archive.

    Notes
    -----
    h/t to https://stackoverflow.com/a/18432983 for the example on converting
    between `TarInfo` and `ZipInfo`.

    Example
    -------
    >>> import tarfile, pygit2
    >>> from gsb import _git
    >>> repo = pygit2.Repository('.')
    >>> with zipfile.ZipFile('foo.zip', 'w') as archive:
    ...     _git.write_zip_archive(repo, repo.head.target, archive)
    """
    # Try to get a tree form whatever we got
    # Try to get a tree form whatever we got
    if isinstance(treeish, (str, Oid)):
        treeish = repo[treeish]

    tree = treeish.peel(Tree)

    # if we don't have a timestamp, try to get it from a commit
    if not timestamp:
        try:
            commit = treeish.peel(Commit)
            timestamp = commit.committer.time
        except Exception:
            pass

    # as a last resort, use the current timestamp
    if not timestamp:
        timestamp = int(time())

    datetime = dt.datetime.fromtimestamp(timestamp)
    zip_datetime = (
        # per https://docs.python.org/3/library/zipfile.html#zipfile.ZipInfo.date_time
        datetime.year,
        datetime.month,
        datetime.day,
        datetime.hour,
        datetime.minute,
        datetime.second,
    )

    index = Index()
    index.read_tree(tree)

    for entry in index:
        content = repo[entry.id].read_raw()
        info = zipfile.ZipInfo(prefix + entry.path)
        info.file_size = len(content)
        info.date_time = zip_datetime
        # info.uname = info.gname = "root"  # git's archive-zip.c does not
        if entry.mode == GIT_FILEMODE_LINK:
            raise NotImplementedError(
                "ZIP archives with symlinks are not currently supported."
                "\nSee: https://bugs.python.org/issue37921"
            )
        # per https://github.com/git/git/blob/3a06386e/archive-zip.c#L339
        info.external_attr = entry.mode << 16 if (entry.mode & 111) else 0
        archive.writestr(info, content)
