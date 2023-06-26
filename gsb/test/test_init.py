"""Tests for creating new repos"""
import pytest

from gsb import onboard
from gsb.manifest import MANIFEST_NAME


class TestFreshInit:
    def test_root_must_be_a_directory(self, tmp_path):
        not_a_dir = tmp_path / "file.txt"
        not_a_dir.write_text("I'm a file\n")

        with pytest.raises(ValueError):
            _ = onboard.create_repo(not_a_dir)

    def test_root_must_exist(self, tmp_path):
        does_not_exist = tmp_path / "phantom"

        with pytest.raises(FileNotFoundError):
            _ = onboard.create_repo(does_not_exist)

    @pytest.fixture
    def root(self, tmp_path):
        root = tmp_path / "rootabaga"
        root.mkdir()
        yield root

    def test_no_pattern_means_add_all(self, root):
        repo, manifest = onboard.create_repo(root)
        assert manifest.patterns == (".",)

    def test_providing_patterns(self, root):
        repo, manifest = onboard.create_repo(root, "savey_mcsavegame", "logs/")
        assert sorted(manifest.patterns) == [
            MANIFEST_NAME,  # I'm assuming that this will always begin with "."
            "savey_mcsavegame",
            "logs/",
        ]

    def test_init_always_creates_a_gitignore(self, root):
        _ = onboard.create_repo(root)
        _ = (root / ".gitignore").read_text()

    def test_providing_ignore(self, root):
        repo, manifest = onboard.create_repo(
            root, "savey_mcsavegame", ignore=[".stuff"]
        )
        ignored = (root / ".gitignore").read_text().splitlines()
        assert ".stuff" in ignored

    def test_repo_must_not_already_exist(self, root):
        _ = onboard.create_repo(root)

        with pytest.raises(FileExistsError):
            _ = onboard.create_repo(root)


class TestInitExistingGitRepo:
    # TODO
    ...
