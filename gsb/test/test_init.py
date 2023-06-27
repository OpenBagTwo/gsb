"""Tests for creating new repos"""
import pytest

from gsb import _git, onboard
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
        manifest = onboard.create_repo(root)
        assert manifest.patterns == (".",)

    def test_providing_patterns(self, root):
        manifest = onboard.create_repo(root, "savey_mcsavegame", "logs/")
        assert manifest.patterns == tuple(
            sorted(
                (
                    ".gitignore",
                    MANIFEST_NAME,
                    "savey_mcsavegame",
                    "logs/",
                )
            )
        )

    def test_init_always_creates_a_gitignore(self, root):
        _ = onboard.create_repo(root)
        _ = (root / ".gitignore").read_text()

    def test_providing_ignore(self, root):
        _ = onboard.create_repo(root, "savey_mcsavegame", ignore=[".stuff"])
        ignored = (root / ".gitignore").read_text().splitlines()
        assert ".stuff" in ignored

    def test_repo_must_not_already_exist(self, root):
        _ = onboard.create_repo(root)

        with pytest.raises(FileExistsError):
            _ = onboard.create_repo(root)

    def test_init_adds_save_contents(self, root):
        (root / "game.sav").write_text("poke\n")
        _ = onboard.create_repo(root, "game.sav")
        index = _git.ls_files(root)
        expected = {root / "game.sav", root / MANIFEST_NAME, root / ".gitignore"}
        assert expected == expected.intersection(index)

    def test_initial_add_respects_gitignore(self, root):
        (root / ".dot_dot").write_text("dash\n")
        _ = onboard.create_repo(root, ignore=[".*"])
        index = _git.ls_files(root)

        assert (root / ".dot_dot") not in index

    def test_initial_add_always_tracks_manifest_and_gitignore(self, root):
        _ = onboard.create_repo(root, ignore=[".*"])
        index = _git.ls_files(root)

        expected = {root / MANIFEST_NAME, root / ".gitignore"}
        assert expected == expected.intersection(index)

    def test_init_performs_initial_commit(self, root):
        _ = onboard.create_repo(root)
        history = _git.log(root, -1)

        assert [commit.message for commit in history] == ["Started tracking with gsb\n"]


class TestInitExistingGitRepo:
    @pytest.fixture
    def existing_repo(self, tmp_path):
        root = tmp_path / "roto-rooter"
        root.mkdir()
        _git.init(root)
        (root / ".gitignore").write_text(
            """# cruft
cruft

# ides
.idea
.borland_turbo
"""
        )
        # TODO: git add and commit to establish a git history
        yield root

    def test_init_is_fine_onboarding_an_existing_git_repo(self, existing_repo):
        _ = onboard.create_repo(existing_repo)

    def test_init_only_appends_to_existing_gitignore(self, existing_repo):
        _ = onboard.create_repo(existing_repo, ignore=["cruft", "stuff"])
        assert (
            (existing_repo / ".gitignore").read_text()
            == """# cruft
cruft

# ides
.idea
.borland_turbo

# gsb
stuff
"""
        )

    @pytest.fixture
    def repo_with_history(self, existing_repo):
        (existing_repo / "game.sav").write_text("chose a squirtle\n")
        _git.add(existing_repo, "game.sav")
        _git.commit(existing_repo, "Initial commit")

        (existing_repo / "game.sav").write_text("take that brock\n")
        _git.add(existing_repo, "game.sav")
        _git.commit(existing_repo, "Checkpoint")

        yield existing_repo

    def test_init_preserves_existing_commits(self, existing_repo):
        _ = onboard.create_repo(existing_repo)
        history = _git.log(existing_repo, -1)

        assert [commit.message for commit in history] == [
            "Started tracking with gsb\n",
            "Checkpoint\n",
            "Initial commit\n",
        ]
