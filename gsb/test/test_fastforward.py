"""Tests for rewriting repo histories"""
import shutil

import pytest

from gsb import fastforward
from gsb.history import get_history
from gsb.rewind import restore_backup


@pytest.fixture(scope="module")
def all_backups(root):
    yield get_history(root, tagged_only=False, include_non_gsb=True)


@pytest.fixture
def cloned_root(root):
    """Because the repo-with-history setup is so expensive, we want to rewrite
    our histories on a copy"""
    destination = root.parent / "cloney"
    shutil.copytree(root, destination)
    yield destination
    shutil.rmtree(destination)


class TestDeleteBackups:
    def test_deleting_a_backup(self, cloned_root):
        fastforward.delete_backups(cloned_root, "gsb1.1")
        assert [revision["identifier"] for revision in get_history(cloned_root)] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.0",
        ]

    def test_deleting_a_backup_doesnt_mess_up_subsequent_backups(self, cloned_root):
        fastforward.delete_backups(cloned_root, "gsb1.1")
        restore_backup(cloned_root, "gsb1.2")  # TODO: replace with export-backup
        assert (cloned_root / "species").read_text() == "\n".join(
            (
                "sauropods",
                "therapods",
                "raptors",
                "pliosaurs",
                "plesiosaurs",
                "mosasaurs",
                "pterosaurs",
            )
        ) + "\n"

    def test_deleting_multiple_backups(self, cloned_root, all_backups):
        # frequent workflow: deleting all non-tagged backups
        fastforward.delete_backups(
            cloned_root,
            *(
                revision["identifier"]
                for revision in all_backups[:-1]
                if not revision["identifier"].startswith(("gsb", "0."))
            )
        )
        assert get_history(cloned_root, tagged_only=False)[:-1] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.1",
            "gsb1.0",
        ]

    def test_raise_value_error_on_invalid_backup(self, cloned_root):
        with pytest.raises(ValueError, match=r"^Could not find((.|\n)*)gsb1.4"):
            fastforward.delete_backups(cloned_root, "gsb1.4")

    @pytest.mark.xfail(reason="not implemented")
    def test_deleting_the_very_first_backup(self, cloned_root, all_backups):
        fastforward.delete_backups(cloned_root, all_backups[-1]["identifier"])

        # can't check strict equality because commit hashes will have changed
        assert (
            len(get_history(cloned_root, tagged_only=False, include_non_gsb=True))
            == len(all_backups) - 1
        )
