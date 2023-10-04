"""Tests for creating new repos"""
import subprocess

import pytest

from gsb import _git, onboard
from gsb.manifest import MANIFEST_NAME, Manifest


class TestFreshInit:
    def test_root_must_be_a_directory(self, tmp_path):
        not_a_dir = tmp_path / "file.txt"
        not_a_dir.write_text("I'm a file\n")

        with pytest.raises(NotADirectoryError):
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

    def test_pattern_with_no_matches_does_not_error(self, root):
        (root / "game.sav").write_text("poke\n")
        _ = onboard.create_repo(root, "save.game")
        index = _git.ls_files(root)
        expected = {root / MANIFEST_NAME, root / ".gitignore"}
        assert expected == expected.intersection(index)

    def test_initial_add_respects_gitignore(self, root):
        (root / ".dot_dot").write_text("dash\n")
        _ = onboard.create_repo(root, ignore=[".*"])
        index = _git.ls_files(root)

        assert (root / ".dot_dot") not in index

    @pytest.mark.parametrize("pattern", (".dot*", "."))
    def test_gitignore_takes_priority_over_patterns_gitignore(self, root, pattern):
        (root / ".dot_dot").write_text("dash\n")
        _ = onboard.create_repo(root, pattern, ignore=[".*"])
        index = _git.ls_files(root)

        assert (root / ".dot_dot") not in index

    def test_initial_add_always_tracks_manifest_and_gitignore(self, root):
        _ = onboard.create_repo(root, ignore=[".*"])
        index = _git.ls_files(root)

        expected = {root / MANIFEST_NAME, root / ".gitignore"}
        assert expected == expected.intersection(index)

    def test_init_performs_initial_commit(self, root):
        _ = onboard.create_repo(root)
        history = _git.log(root)

        assert [commit.message for commit in history] == ["Start of gsb tracking\n"]

    def test_init_tags_that_initial_commit(self, root):
        _ = onboard.create_repo(root)
        tags = _git.get_tags(root, annotated_only=False)

        assert [tag.annotation for tag in tags] == ["Start of gsb tracking\n"]

    def test_branch_name_is_gsb_for_fresh_repo(self, root):
        _ = onboard.create_repo(root)
        assert _git._repo(root).head.shorthand == "gsb"


class TestInitExistingGitRepo:
    @pytest.fixture
    def existing_repo(self, tmp_path):
        root = tmp_path / "roto-rooter"
        root.mkdir()
        _git._repo(root, new=True, initial_branch="main")
        (root / ".gitignore").write_text(
            """# cruft
cruft

# ides
.idea
.borland_turbo
"""
        )
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
        _git.add(existing_repo, ["game.sav"])
        _git.commit(existing_repo, "Initial commit")
        _git.tag(existing_repo, "v0.0.1", "F1rst")

        (existing_repo / "game.sav").write_text("take that brock\n")
        _git.add(existing_repo, ["game.sav"])
        _git.commit(existing_repo, "Checkpoint")
        _git.tag(existing_repo, "v0.0.1+1", None)

        yield existing_repo

    def test_init_preserves_existing_commits(self, repo_with_history):
        _ = onboard.create_repo(repo_with_history)
        history = _git.log(repo_with_history)

        assert [commit.message for commit in history] == [
            "Start of gsb tracking\n",
            "Checkpoint\n",
            "Initial commit\n",
        ]

    def test_init_does_not_change_branch_name(self, repo_with_history):
        _ = onboard.create_repo(repo_with_history)
        assert _git._repo(repo_with_history).head.shorthand == "main"

    @pytest.mark.parametrize(
        "include_lightweight", (True, False), ids=("all", "annotated")
    )
    def test_init_preserves_existing_tags(self, repo_with_history, include_lightweight):
        _ = onboard.create_repo(repo_with_history)
        tags = _git.get_tags(repo_with_history, annotated_only=not include_lightweight)

        expected = {"F1rst\n", "Start of gsb tracking\n"}
        if include_lightweight:
            expected.add(None)

        assert {tag.annotation for tag in tags} == expected


class TestCLI:
    @pytest.fixture
    def root(self, tmp_path):
        root = tmp_path / "froot"
        root.mkdir()
        (root / "toot").touch()
        yield root

    def test_init_in_cwd_by_default(self, root):
        subprocess.run(["gsb", "init"], cwd=root)
        assert (root / ".git").exists()

    def test_passing_in_a_custom_root_by_option(self, root):
        subprocess.run(["gsb", "init", "--path", root.name], cwd=root.parent)
        assert (root / ".git").exists()

    @pytest.mark.parametrize(
        "how", ("by_argument", "by_option", "by_option_individually", "mixed")
    )
    def test_passing_in_track_patterns(self, root, how):
        patterns = {"toot", "soot", "foot", "*oot/**"}
        args = ["gsb", "init", *patterns]
        if how.startswith("by_option"):
            args.insert(2, "--track")
        if how == "by_option_individually":
            for i in range(1, len(patterns)):
                args.insert(2 + 2 * i, "--track")
        if how == "mixed":
            args.insert(2 + len(patterns) // 2, "--track")

        subprocess.run(args, cwd=root)

        written_patterns = set(Manifest.of(root).patterns)

        assert patterns.intersection(written_patterns) == patterns

    def test_passing_in_ignores(self, root):
        patterns = {"scoot", "flute"}
        args = ["gsb", "init"]
        for pattern in patterns:
            args.extend(("--ignore", pattern))

        subprocess.run(args, cwd=root)

        written_patterns = set((root / ".gitignore").read_text().splitlines())

        assert patterns.intersection(written_patterns) == patterns

    def test_mixing_includes_and_ignores(self, root):
        subprocess.run(
            [
                "gsb",
                "init",
                "toot",
                "--ignore",
                "flute",
                "--track",
                "boot",
                "*oot/**",
                "--ignore",
                "scoot",
                "--path",
                str(root.absolute()),
            ]
        )

        includes = set(Manifest.of(root).patterns)
        ignores = set((root / ".gitignore").read_text().splitlines())

        expected_includes = {"toot", "boot", "*oot/**"}
        expected_ignores = {"flute", "scoot"}
        assert expected_includes.intersection(includes) == expected_includes
        assert expected_ignores.intersection(ignores) == expected_ignores
        assert expected_includes.intersection(ignores) == set()
        assert expected_ignores.intersection(includes) == set()
