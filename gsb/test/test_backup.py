"""Tests for creating backups"""
import os
import subprocess
from pathlib import Path

import pygit2
import pytest

from gsb import _git, backup, onboard


@pytest.fixture
def repo_root(tmp_path):
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


@pytest.mark.usefixtures("patch_tag_naming")
class TestCreateBackup:
    @pytest.mark.parametrize("root_type", ("no_folder", "no_git", "no_manifest"))
    def test_raises_when_theres_no_gsb_repo(self, tmp_path, root_type):
        random_folder = tmp_path / "random folder"
        if root_type != "no_folder":
            random_folder.mkdir()
        if root_type == "no_manifest":
            _git.init(random_folder)
        with pytest.raises(OSError):
            backup.create_backup(random_folder)

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

    def test_raise_when_theres_nothing_new_to_backup(self, repo_root):
        backup.create_backup(repo_root)
        with pytest.raises(ValueError):
            backup.create_backup(repo_root)

    def test_tagging_a_previously_untagged_backup(self, repo_root):
        hash = backup.create_backup(repo_root)
        tag_name = backup.create_backup(repo_root, "You're it")

        repo = _git._repo(repo_root, new=False)
        assert str(repo.revparse_single(tag_name).target) == hash


class TestCLI:
    @pytest.fixture
    def prior_commits(self, repo_root):
        yield list(_git.log(repo_root))

    @pytest.fixture
    def prior_tags(self, repo_root):
        yield list(_git.get_tags(repo_root, False))

    def test_default_options_creates_untagged_backup_from_cwd(
        self, repo_root, prior_commits, prior_tags
    ):
        subprocess.run(["gsb", "backup"], cwd=repo_root)

        assert (
            len(list(_git.log(repo_root))),
            len(list(_git.get_tags(repo_root, False))),
        ) == (
            len(prior_commits) + 1,
            len(prior_tags),
        )

    @pytest.mark.parametrize("how", ("by_argument", "by_option"))
    def test_passing_in_a_custom_root(self, repo_root, how, prior_commits):
        args = ["gsb", "backup", repo_root]
        if how == "by_option":
            args.insert(2, "--path")

        subprocess.run(args)

        assert len(list(_git.log(repo_root))) == len(prior_commits) + 1

    @pytest.mark.usefixtures("patch_tag_naming")
    def test_creating_a_tagged_backup(self, repo_root, prior_commits, prior_tags):
        if os.name == "posix":
            subprocess.run(
                ['gsb backup --tag "Hello World"'], cwd=repo_root, shell=True
            )
        else:
            subprocess.run(["gsb", "backup", "--tag", "Hello World"], cwd=repo_root)

        tags = list(_git.get_tags(repo_root, False))

        assert (
            len(list(_git.log(repo_root))),
            len(tags),
        ) == (
            len(prior_commits) + 1,
            len(prior_tags) + 1,
        )

        assert tags[-1].annotation == "Hello World\n"
