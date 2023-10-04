"""Tests for rewriting repo histories"""
import logging
import shutil
import subprocess

import pytest

from gsb import _git, fastforward
from gsb.backup import create_backup
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

    @pytest.mark.usefixtures("patch_tag_naming")
    def test_deleting_a_backup_preserves_subsequent_backup_timestamps(
        self, cloned_root, jurassic_timestamp
    ):
        fastforward.delete_backups(cloned_root, "gsb1.0")
        assert [
            revision["identifier"]
            for revision in get_history(cloned_root, since=jurassic_timestamp)
        ] == ["gsb1.3", "gsb1.2"]

    def test_deleting_multiple_backups(self, cloned_root, all_backups):
        # frequent workflow: deleting all non-tagged backups
        fastforward.delete_backups(
            cloned_root,
            *(
                revision["identifier"]
                for revision in all_backups[:-1]
                if not revision["identifier"].startswith(("gsb", "0."))
            ),
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

    def test_branch_post_ff_is_gsb(self, cloned_root, caplog):
        fastforward.delete_backups(cloned_root, "gsb1.0")
        assert _git._repo(cloned_root).head.shorthand == "gsb"
        assert "Could not delete branch" in "\n".join(
            [
                record.message
                for record in caplog.records
                if record.levelno == logging.WARNING
            ]
        )

    def test_original_non_gsb_branch_is_not_deleted(self, cloned_root):
        fastforward.delete_backups(cloned_root, "0.2")
        assert "main" in _git._repo(cloned_root).branches.local


class TestCLI:
    def test_no_args_initiates_prompt_in_cwd(self, cloned_root):
        result = subprocess.run(
            ["gsb", "delete"],
            cwd=cloned_root,
            capture_output=True,
            input="q\n".encode(),
        )

        assert (
            "Select one by identifier, or multiple separated by commas"
            in result.stderr.decode().strip().splitlines()[-2]
        )

    def test_prompt_includes_all_commits_since_last_tag(self, cloned_root):
        (cloned_root / "continents").write_text(
            "\n".join(
                (
                    "laurasia",
                    "gondwana",
                )
            )
            + "\n"
        )
        Manifest.of(cloned_root)._replace(
            patterns=("species", "continents", "oceans")
        ).write()
        create_backup(cloned_root)
        (cloned_root / "oceans").write_text(
            "\n".join(
                (
                    "pacific",
                    "tethys",
                )
            )
            + "\n"
        )
        create_backup(cloned_root)

        result = subprocess.run(
            ["gsb", "delete"],
            cwd=cloned_root,
            capture_output=True,
            input="q\n".encode(),
        )
        # there should be two untagged backups after the latest tagged backup
        assert "gsb1.3" in result.stderr.decode().strip().splitlines()[-3 - 2]

    def test_passing_in_a_custom_root(self, cloned_root):
        result = subprocess.run(
            ["gsb", "delete", "--path", cloned_root.name, "0.2"],
            cwd=cloned_root.parent,
            capture_output=True,
            input="q\n".encode(),
        )

        assert (
            get_history(cloned_root, tagged_only=True, include_non_gsb=True)[-2][
                "identifier"
            ]
            == "gsb1.0"
        )

    def test_deleting_tag_by_argument(self, cloned_root):
        _ = subprocess.run(
            ["gsb", "delete", "gsb1.1"], cwd=cloned_root, capture_output=True
        )

        assert [
            backup["identifier"]
            for backup in get_history(cloned_root, tagged_only=True, limit=3)
        ] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.0",
        ]

    @pytest.mark.parametrize(
        "how",
        (
            "short",
            "full",
        ),
    )
    def test_deleting_by_commit(self, cloned_root, how):
        some_commit = list(_git.log(cloned_root))[2].hash

        # meta-test to make sure I didn't grab a tag
        assert some_commit not in {
            tag.target for tag in _git.get_tags(cloned_root, annotated_only=True)
        }

        if how == "short":
            some_commit = some_commit[:8]

        _ = subprocess.run(
            ["gsb", "delete", some_commit],
            cwd=cloned_root,
            capture_output=True,
        )

        assert [
            backup["identifier"]
            for backup in get_history(cloned_root, tagged_only=False, limit=3)[::2]
        ] == [
            "gsb1.3",
            "gsb1.2",
        ]

    def test_deleting_by_prompt(self, cloned_root):
        _ = subprocess.run(
            ["gsb", "delete"],
            cwd=cloned_root,
            capture_output=True,
            input="gsb1.0\n".encode(),
        )

        assert [
            backup["identifier"]
            for backup in get_history(cloned_root, tagged_only=True)
        ] == [
            "gsb1.3",
            "gsb1.2",
            "0.2",
        ]

    @pytest.mark.parametrize("how", ("by_argument", "by_prompt"))
    def test_unknown_revision_raises_error(self, cloned_root, how):
        arguments = ["gsb", "delete"]
        response = ""
        if how == "by_argument":
            arguments.append("gsb1.4")
        else:  # if how == "by_prompt"
            response = "gsb1.4\n"

        result = subprocess.run(
            arguments,
            cwd=cloned_root,
            capture_output=True,
            input=response.encode(),
        )

        assert result.returncode == 1
        assert "gsb1.4" in result.stderr.decode().strip().splitlines()[-1]

    @pytest.mark.parametrize("how", ("by_argument", "by_prompt"))
    def test_multi_delete(self, cloned_root, how):
        arguments = ["gsb", "delete"]
        response = ""
        if how == "by_argument":
            arguments.extend(["gsb1.0", "gsb1.1", "gsb1.2"])
        else:  # if how == "by_prompt"
            response = "gsb1.0, gsb1.1,gsb1.2\n"

        _ = subprocess.run(
            arguments,
            cwd=cloned_root,
            capture_output=True,
            input=response.encode(),
        )

        assert [
            backup["identifier"]
            for backup in get_history(
                cloned_root, tagged_only=True, include_non_gsb=True
            )
        ] == ["gsb1.3", "0.2", "0.1"]

    def test_running_on_repo_with_no_tags_retrieves_gsb_commits(self, tmp_path):
        """Like, I guess if the user deleted the initial backup"""
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)
        _git.add(repo, [something.name])
        commit_hash = _git.commit(repo, "Hello").hash[:8]

        result = subprocess.run(
            ["gsb", "delete"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        assert f"{commit_hash}" in result.stderr.decode().strip().splitlines()[1]

    def test_running_on_non_gsb_prompts_with_git_commits(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)
        _git.add(repo, [something.name])
        commit_hash = _git.commit(repo, "Hello", _committer=("Testy", "Testy")).hash[:8]

        result = subprocess.run(
            ["gsb", "delete"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        log_lines = result.stderr.decode().strip().splitlines()

        assert "No gsb revisions found" in log_lines[1]
        assert f"{commit_hash}" in log_lines[2]

    def test_running_on_empty_repo_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)

        result = subprocess.run(["gsb", "delete"], cwd=repo, capture_output=True)
        assert result.returncode == 1
        assert "No revisions found" in result.stderr.decode().strip().splitlines()[-1]

    def test_deleting_tells_you_to_run_git_gc_when_done(self, cloned_root):
        result = subprocess.run(
            ["gsb", "delete", "gsb1.1"], cwd=cloned_root, capture_output=True
        )

        assert "git gc" in result.stderr.decode().strip().splitlines()[-1]
