"""Tests for rewriting repo histories"""
import logging
import subprocess

import pytest

from gsb import _git, fastforward
from gsb.backup import create_backup
from gsb.history import get_history
from gsb.rewind import restore_backup


class TestDeleteBackups:
    def test_deleting_a_backup(self, root):
        fastforward.delete_backups(root, "gsb1.1")
        assert [revision["identifier"] for revision in get_history(root)] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.0",
        ]

    def test_modified_files_are_automatically_backed_up(self, root):
        fastforward.delete_backups(root, "gsb1.3")

        # make sure the backup was deleted
        assert [revision["identifier"] for revision in get_history(root, limit=2)] == [
            "gsb1.2",
            "gsb1.1",
        ]

        # make sure there's nothing to commit post-ff
        _git.add(root, ["oceans"])
        with pytest.raises(ValueError, match="Nothing to commit"):
            _git.commit(root, "Oh no! Continents weren't being tracked!")

        # make sure that the unsaved contents were backed up (and preserved)
        assert [
            line.strip() for line in (root / "oceans").read_text("utf-8").splitlines()
        ] == [
            "pacific",
            "tethys",
        ]

    @pytest.mark.usefixtures("patch_tag_naming")
    def test_deleting_a_backup_doesnt_mess_up_subsequent_backups(self, root):
        fastforward.delete_backups(root, "gsb1.1")
        restore_backup(root, "gsb1.2")  # TODO: replace with export-backup
        assert (root / "species").read_text() == "\n".join(
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
        self, root, jurassic_timestamp
    ):
        fastforward.delete_backups(root, "gsb1.0")
        assert [
            revision["identifier"]
            for revision in get_history(root, since=jurassic_timestamp)
        ] == ["gsb1.3", "gsb1.2"]

    def test_deleting_multiple_backups(self, root, all_backups):
        _git.reset(root, "gsb1.3", hard=True)

        # frequent workflow: deleting all non-tagged backups
        fastforward.delete_backups(
            root,
            *(
                revision["identifier"]
                for revision in all_backups[1:-1]
                if not revision["identifier"].startswith(("gsb", "0."))
            ),
        )
        assert [
            backup["identifier"] for backup in get_history(root, tagged_only=False)
        ] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.1",
            "gsb1.0",
            "0.2",
            "0.1",
        ]

    def test_raise_value_error_on_invalid_backup(self, root):
        with pytest.raises(ValueError, match=r"^Could not find((.|\n)*)gsb1.4"):
            fastforward.delete_backups(root, "gsb1.4")

    @pytest.mark.xfail(reason="not implemented")
    def test_deleting_the_very_first_backup(self, root, all_backups):
        fastforward.delete_backups(root, all_backups[-1]["identifier"])

        # can't check strict equality because commit hashes will have changed
        assert (
            len(get_history(root, tagged_only=False, include_non_gsb=True))
            == len(all_backups) - 1
        )

    def test_branch_post_ff_is_gsb(self, root, caplog):
        fastforward.delete_backups(root, "gsb1.0")
        assert _git._repo(root).head.shorthand == "gsb"
        assert "Could not delete branch" in "\n".join(
            [
                record.message
                for record in caplog.records
                if record.levelno == logging.WARNING
            ]
        )

    def test_original_non_gsb_branch_is_not_deleted(self, root):
        fastforward.delete_backups(root, "0.2")
        assert "main" in _git._repo(root).branches.local

    def test_cant_delete_backup_from_outside_history(self, root):
        _git.checkout_branch(root, "gsb", "gsb1.1")
        with pytest.raises(ValueError, match="not within the linear commit history"):
            fastforward.delete_backups(root, "gsb1.2")


class TestCLI:
    def test_no_args_initiates_prompt_in_cwd(self, root):
        result = subprocess.run(
            ["gsb", "delete"],
            cwd=root,
            capture_output=True,
            input="q\n".encode(),
        )

        assert (
            "Select a revision or revisions"
            in result.stdout.decode().strip().splitlines()[-1]
        )

    def test_prompt_includes_all_commits_since_last_tag(self, root, all_backups):
        post_tag_backup_1 = all_backups[0]["identifier"]
        post_tag_backup_2 = create_backup(root)[:8]

        result = subprocess.run(
            ["gsb", "delete"],
            cwd=root,
            capture_output=True,
            input="q\n".encode(),
        )
        assert [
            f"- {post_tag_backup_2}",
            f"- {post_tag_backup_1}",
            "- gsb1.3",
        ] == [
            line.split("from")[0].strip()
            for line in result.stderr.decode().strip().splitlines()[1:4]
        ]

    def test_passing_in_a_custom_root(self, root):
        _ = subprocess.run(
            ["gsb", "delete", "--path", root.name, "0.2"],
            cwd=root.parent,
            capture_output=True,
            input="q\n".encode(),
        )

        assert (
            get_history(root, tagged_only=True, include_non_gsb=True)[-2]["identifier"]
            == "gsb1.0"
        )

    def test_deleting_tag_by_argument(self, root):
        _ = subprocess.run(["gsb", "delete", "gsb1.1"], cwd=root, capture_output=True)

        assert [
            backup["identifier"]
            for backup in get_history(root, tagged_only=True, limit=3)
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
    def test_deleting_by_commit(self, root, how, all_backups):
        _git.reset(root, "gsb1.3", hard=True)  # reset to just after tagged bkp
        some_backup = all_backups[2]

        # meta-test to make sure I didn't grab a tag
        assert not some_backup["tagged"]

        if how == "short":
            some_commit = some_backup["identifier"]
        else:
            some_commit = some_backup["commit_hash"]

        _ = subprocess.run(
            ["gsb", "delete", some_commit],
            cwd=root,
            capture_output=True,
        )

        assert [
            backup["identifier"]
            for backup in get_history(root, tagged_only=False, limit=3)[::2]
        ] == [
            "gsb1.3",
            "gsb1.2",
        ]

    def test_deleting_by_prompt(self, root):
        _ = subprocess.run(
            ["gsb", "delete"],
            cwd=root,
            capture_output=True,
            input="gsb1.1\n".encode(),
        )

        assert [
            backup["identifier"] for backup in get_history(root, tagged_only=True)
        ] == [
            "gsb1.3",
            "gsb1.2",
            "gsb1.0",
        ]

    @pytest.mark.parametrize("how", ("by_argument", "by_prompt"))
    def test_unknown_revision_raises_error(self, root, how):
        arguments = ["gsb", "delete"]
        response = ""
        if how == "by_argument":
            arguments.append("gsb1.4")
        else:  # if how == "by_prompt"
            response = "gsb1.4\n"

        result = subprocess.run(
            arguments,
            cwd=root,
            capture_output=True,
            input=response.encode(),
        )

        assert result.returncode == 1
        assert "gsb1.4" in result.stderr.decode().strip().splitlines()[-1]

    @pytest.mark.parametrize("how", ("by_argument", "by_prompt"))
    def test_multi_delete(self, root, how):
        arguments = ["gsb", "delete"]
        response = ""
        if how == "by_argument":
            arguments.extend(["gsb1.0", "gsb1.1", "gsb1.2"])
        else:  # if how == "by_prompt"
            response = "gsb1.0, gsb1.1,gsb1.2\n"

        _ = subprocess.run(
            arguments,
            cwd=root,
            capture_output=True,
            input=response.encode(),
        )

        assert [
            backup["identifier"]
            for backup in get_history(root, tagged_only=True, include_non_gsb=True)
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

        assert "No GSB revisions found" in log_lines[1]
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

    def test_deleting_tells_you_to_run_git_gc_when_done(self, root):
        result = subprocess.run(
            ["gsb", "delete", "gsb1.1"], cwd=root, capture_output=True
        )

        assert "git gc" in result.stderr.decode().strip().splitlines()[-1]
