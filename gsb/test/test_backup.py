"""Tests for creating backups"""
import os
import subprocess
from pathlib import Path

import pygit2
import pytest

from gsb import _git, backup, onboard
from gsb.history import get_history
from gsb.manifest import Manifest


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

        backup.create_backup(repo_root, tag_message="You're it" if tagged else None)

        repo = _git._repo(repo_root, new=False)
        assert repo_root / "my world" / "new file" in [
            Path(repo_root) / entry.path for entry in repo.index
        ]

    @pytest.mark.parametrize("tagged", (True, False), ids=("tagged", "untagged"))
    def test_backup_respects_gitignore(self, repo_root, tagged):
        backup.create_backup(repo_root, tag_message="You're it" if tagged else None)

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
        commit_hash = backup.create_backup(repo_root)
        tag_name = backup.create_backup(repo_root, "You're it")

        repo = _git._repo(repo_root, new=False)
        assert str(repo.revparse_single(tag_name).target) == commit_hash

    def test_combining_with_previous_backup(self, root):
        identifier = backup.create_backup(root, parent="gsb1.3")
        assert [
            revision["identifier"]
            for revision in get_history(
                root, tagged_only=False, include_non_gsb=True, limit=2
            )
        ] == [identifier[:8], "gsb1.3"]

        # ensure that the squash kept all file changes
        assert (root / "continents").read_text("utf-8").startswith("laurasia")
        assert "oceans" in Manifest.of(root).patterns
        assert (root / "oceans").read_text("utf-8").strip().endswith("tethys")


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

    def test_squash_with_last_commit(self, root):
        result = subprocess.run(["gsb", "backup", "-vc"], cwd=root, capture_output=True)
        commit_id = result.stderr.decode().splitlines()[-1].split("hash")[-1].strip()

        assert [
            revision["identifier"]
            for revision in get_history(
                root, tagged_only=False, include_non_gsb=True, limit=2
            )
        ] == [commit_id, "gsb1.3"]

    @pytest.mark.parametrize("confirm", (False, True), ids=("abort", "confirm"))
    def test_squash_with_last_tag_requires_confirmation(self, root, confirm):
        _git.reset(root, "gsb1.3", hard=False)

        result = subprocess.run(
            ["gsb", "backup", "-c"],
            cwd=root,
            capture_output=True,
            input=("y\n" if confirm else "\n").encode(),
        )

        if confirm:
            assert "gsb1.3" not in {
                tag.name for tag in _git.get_tags(root, annotated_only=False)
            }
        else:
            assert "Aborting" in result.stderr.decode().splitlines()[-1]

            assert (
                get_history(root, tagged_only=False, include_non_gsb=True, limit=1)[0][
                    "identifier"
                ]
                == "gsb1.3"
            )

    @pytest.mark.xfail(reason="not implemented")
    def test_squashing_with_the_first_backup(self, tmp_path):
        repo = tmp_path / "fresh"
        repo.mkdir()
        onboard.create_repo(repo, "something")
        result = subprocess.run(
            ["gsb", "backup", "-c"], cwd=repo, capture_output=True, input="y\n".encode()
        )
        assert result.returncode == 0
        assert len(get_history(repo, tagged_only=False)) == 1

    def test_squash_all_since_last_tag(self, root):
        # commit unsaved changes, so we can test that -cc works
        # even when all we're doing is squashing
        backup.create_backup(root)

        result = subprocess.run(
            ["gsb", "backup", "-vcc"], cwd=root, capture_output=True
        )
        commit_id = result.stderr.decode().splitlines()[-1].split("hash")[-1].strip()

        assert [
            revision["identifier"]
            for revision in get_history(
                root, tagged_only=False, include_non_gsb=True, limit=2
            )
        ] == [commit_id, "gsb1.3"]

    def test_squash_all_since_last_tag_is_quiet_when_theres_nothing_to_squash(
        self, root
    ):
        _git.reset(root, "gsb1.3", hard=False)

        result = subprocess.run(
            ["gsb", "backup", "-qcc"], cwd=root, capture_output=True
        )

        assert not result.stderr.decode()

        assert (
            get_history(root, tagged_only=False, include_non_gsb=True, limit=2)[-1][
                "identifier"
            ]
            == "gsb1.3"
        )

    def test_squash_all_since_last_tag_raises_when_there_are_no_tags(self, tmp_path):
        repo = tmp_path / "fresh"
        repo.mkdir()
        _git.init(repo)
        (repo / ".gitignore").touch()
        Manifest(repo, ("something",)).write()
        backup.create_backup(repo)
        (repo / "something").write_text("it's not nothing\n")
        backup.create_backup(repo)
        result = subprocess.run(["gsb", "backup", "-cc"], cwd=repo, capture_output=True)
        assert result.returncode == 1
        assert len(get_history(repo, tagged_only=False)) == 2
