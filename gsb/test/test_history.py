"""Tests for reviewing repo histories"""
import subprocess

import pytest

from gsb import history
from gsb.backup import create_backup
from gsb.manifest import Manifest


class TestGetHistory:
    @pytest.mark.parametrize("create_root", (True, False), ids=("no_git", "no_folder"))
    def test_raises_when_theres_no_git_repo(self, tmp_path, create_root):
        random_folder = tmp_path / "random folder"
        if create_root:
            random_folder.mkdir()
        with pytest.raises(OSError):
            history.get_history(random_folder)

    def test_get_history_by_default_returns_all_gsb_tags(self, root):
        assert [revision["identifier"] for revision in history.get_history(root)] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.1",
            "gsb1.0",
        ]

    def test_get_history_can_limit_the_number_of_revisions(self, root):
        assert [
            revision["identifier"] for revision in history.get_history(root, limit=1)
        ] == ["gsb1.3"]

    def test_get_history_can_limit_revisions_by_date(self, root, jurassic_timestamp):
        assert [
            revision["identifier"]
            for revision in history.get_history(root, since=jurassic_timestamp)
        ] == ["gsb1.3", "gsb1.2"]

    def test_get_history_can_return_interim_commits_as_well(self, root):
        assert [
            revision["description"]
            for revision in history.get_history(root, tagged_only=False)
        ] == [
            "Cretaceous (my gracious!)",
            "Autocommit",
            "Jurassic",
            "Autocommit",
            "Triassic",
            "Start of gsb tracking",
        ]

    def test_get_history_can_return_non_gsb_tags_as_well(self, root):
        assert [
            revision["identifier"]
            for revision in history.get_history(root, include_non_gsb=True)
        ] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.1",
            "gsb1.0",
            "0.2",
            "0.1",
        ]

    def test_get_history_can_return_non_gsb_commits_as_well(self, root):
        assert [
            revision["description"]
            for revision in history.get_history(
                root, tagged_only=False, include_non_gsb=True, limit=2
            )
        ] == [
            "Cretaceous (my gracious!)",
            "It's my ancestors!",
        ]

    def test_getting_revisions_since_last_tagged_backup(self, root):
        (root / "continents").write_text(
            "\n".join(
                (
                    "laurasia",
                    "gondwana",
                )
            )
            + "\n"
        )
        Manifest.of(root)._replace(patterns=("species", "continents", "oceans")).write()
        create_backup(root)
        (root / "oceans").write_text(
            "\n".join(
                (
                    "pacific",
                    "tethys",
                )
            )
            + "\n"
        )
        create_backup(root)

        assert (
            len(
                history.get_history(
                    root, tagged_only=False, since_last_tagged_backup=True
                )
            )
            == 2
        )


class TestCLI:
    def test_default_options_returns_all_gsb_tags_for_the_cwd(self, root):
        result = subprocess.run(["gsb", "history"], cwd=root, capture_output=True)
        backups = [
            line.split(" from ")[0] for line in result.stderr.decode().splitlines()
        ]
        assert backups == ["1. gsb1.3", "2. gsb1.2", "3. gsb1.1", "4. gsb1.0"]

    @pytest.mark.parametrize("how", ("by_argument", "by_option"))
    def test_passing_in_a_custom_root(self, root, how):
        args = ["gsb", "history", root]
        if how == "by_option":
            args.insert(2, "--path")

        result = subprocess.run(args, capture_output=True)

        assert result.stderr.decode().splitlines()[0].startswith("1. gsb1.3")

    @pytest.mark.parametrize("flag", ("--limit", "-n", "-n1"))
    def test_setting_a_limit(self, root, flag):
        args = ["gsb", "history", flag]
        if flag != "-n1":
            args.append("1")

        result = subprocess.run(args, capture_output=True, cwd=root)

        backups = [
            line.split(" from ")[0] for line in result.stderr.decode().splitlines()
        ]
        assert backups == ["1. gsb1.3"]

    @pytest.mark.parametrize("flag", ("--limit", "-n", "-n0"))
    def test_raise_when_an_invalid_limit_is_set(self, root, flag):
        args = ["gsb", "history", flag]
        if flag != "-n0":
            args.append("-1")

        result = subprocess.run(args, capture_output=True, cwd=root)

        assert "Limit must be a positive integer" in result.stderr.decode()

    def test_setting_since(self, root, jurassic_timestamp):
        args = ["gsb", "history", "--since", jurassic_timestamp.isoformat()]

        result = subprocess.run(args, capture_output=True, cwd=root)

        backups = [
            line.split(" from ")[0] for line in result.stderr.decode().splitlines()
        ]
        assert backups == ["1. gsb1.3", "2. gsb1.2"]

    @pytest.mark.parametrize("flag", ("--include_non_gsb", "-g"))
    def test_including_non_gsb(self, root, flag):
        args = ["gsb", "history", flag]

        result = subprocess.run(args, capture_output=True, cwd=root)

        backups = [
            line.split(" from ")[0] for line in result.stderr.decode().splitlines()
        ]
        assert backups == [
            "1. gsb1.3",
            "2. gsb1.2",
            "3. gsb1.1",
            "4. gsb1.0",
            "5. 0.2",
            "6. 0.1",
        ]

    @pytest.mark.parametrize("flag", ("--all", "-a"))
    def test_including_commits(self, root, flag):
        args = ["gsb", "history", flag]

        result = subprocess.run(args, capture_output=True, cwd=root)

        backups = [
            line.split(" from ")[0]
            for line in [result.stderr.decode().splitlines()[i] for i in [0, 2, 4, 5]]
        ]
        assert backups == [
            "1. gsb1.3",
            "3. gsb1.2",
            "5. gsb1.1",
            "6. gsb1.0",
        ]
