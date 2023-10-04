"""Tests for rewriting repo histories"""
import shutil

import pytest

from gsb import _git, fastforward
from gsb.history import get_history
from gsb.manifest import Manifest
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

    def test_modified_files_are_automatically_backed_up(self, cloned_root):
        cretaceous_continents = (
            "\n".join(
                (
                    "laurasia",
                    "gondwana",
                )
            )
            + "\n"
        )

        (cloned_root / "continents").write_text(cretaceous_continents)
        Manifest.of(cloned_root)._replace(patterns=("species", "continents")).write()
        fastforward.delete_backups(cloned_root, "gsb1.3")

        # make sure the backup was deleted
        assert [
            revision["identifier"] for revision in get_history(cloned_root, limit=2)
        ] == [
            "gsb1.2",
            "gsb1.1",
        ]

        # make sure there's nothing to commit post-ff
        _git.add(cloned_root, ["continents"])
        with pytest.raises(ValueError, match="Nothing to commit"):
            _git.commit(cloned_root, "Oh no! Continents weren't being tracked!")

        # make sure that the unsaved contents were backed up (and preserved)
        assert (cloned_root / "continents").read_text("utf-8") == cretaceous_continents

    @pytest.mark.usefixtures("patch_tag_naming")
    def test_deleting_a_backup_doesnt_mess_up_subsequent_backups(self, cloned_root):
        fastforward.delete_backups(cloned_root, "gsb1.1")
        restore_backup(cloned_root, "gsb1.2")  # TODO: replace with export-backup
        assert (cloned_root / "species").read_text() == "\n".join(
            (
                "sauropods",
                "therapods",
                "plesiosaurs",
                "pterosaurs",
                "squids",
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
        assert [
            backup["identifier"]
            for backup in get_history(cloned_root, tagged_only=False)[:-1]
        ] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.1",
            "gsb1.0",
            "0.2",
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
