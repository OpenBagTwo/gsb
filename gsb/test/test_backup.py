"""Tests for creating backups"""
from pathlib import Path

import pygit2
import pytest

from gsb import _git, backup, onboard


@pytest.mark.usefixtures("patch_tag_naming")
class TestCreateBackup:
    @pytest.mark.parametrize("root_type", ("no_folder", "no_git", "no_manifest"))
    def test_raises_when_theres_no_git_repo(self, tmp_path, root_type):
        random_folder = tmp_path / "random folder"
        if root_type != "no_folder":
            random_folder.mkdir()
        if root_type == "no_manifest":
            _git.init(random_folder)
        with pytest.raises(OSError):
            backup.create_backup(random_folder)

    @pytest.fixture
    def repo_root(self, tmp_path):
        root = tmp_path / "roto-rooter"

        my_world = root / "my world"
        my_world.mkdir(parents=True)

        my_save_data = my_world / "level.dat"
        my_save_data.write_text("Spawn Point: (0, 63, 0)\n")

        onboard.create_repo(root, my_world.name, ignore=["cruft", "ignore me"])

        my_save_data.write_text("Coordinates: (20, 71, -104)\n")

        (my_world / "new file").write_text("Hello, I'm new.\n")

        (my_world / "cruft").write_text("Boilerplate\n")

        ignoreme = my_world / "ignore me"
        ignoreme.mkdir()
        (ignoreme / "content.txt").write_text("Shouting into the void\n")

        yield root

    @pytest.mark.parametrize("tagged", (True, False), ids=("tagged", "untagged"))
    def test_backup_adds_from_manifest(self, repo_root, tagged):
        repo = _git._repo(repo_root, new=False)
        assert repo_root / "my world" / "new file" not in [
            Path(repo_root) / entry.path for entry in repo.index
        ]

        backup.create_backup(repo_root, tag="You're it" if tagged else None)

        repo = _git._repo(repo_root, new=False)
        assert repo_root / "my world" / "new file" in [
            Path(repo_root) / entry.path for entry in repo.index
        ]

    @pytest.mark.parametrize("tagged", (True, False), ids=("tagged", "untagged"))
    def test_backup_respects_gitignore(self, repo_root, tagged):
        backup.create_backup(repo_root, tag="You're it" if tagged else None)

        repo = _git._repo(repo_root, new=False)
        assert repo_root / "my world" / "ignore me" / "content.txt" not in [
            Path(repo_root) / entry.path for entry in repo.index
        ]

    def test_untagged_backup_is_a_commit(self, repo_root):
        identifier = backup.create_backup(repo_root)

        repo = _git._repo(repo_root, new=False)
        assert repo[identifier].type == pygit2.GIT_OBJ_COMMIT

    def test_tagged_backup_is_a_tag(self, repo_root):
        identifier = backup.create_backup(repo_root, "You're it")

        repo = _git._repo(repo_root, new=False)
        assert repo.revparse_single(identifier).type == pygit2.GIT_OBJ_TAG

    def test_tagging_a_previously_untagged_backup(self, repo_root):
        hash = backup.create_backup(repo_root)
        tag_name = backup.create_backup(repo_root, "You're it")

        repo = _git._repo(repo_root, new=False)
        assert repo.revparse_single(tag_name).target == hash
