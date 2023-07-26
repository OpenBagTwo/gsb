"""Tests for restoring backups"""
import subprocess

import pytest

from gsb import _git, backup, history, onboard, rewind


@pytest.fixture
def repo(tmp_path, patch_tag_naming):
    my_game_data = tmp_path / "best game ever"
    my_save_data = my_game_data / "save" / "data.txt"
    my_save_data.parent.mkdir(parents=True)
    my_save_data.touch()
    onboard.create_repo(my_game_data, "save")

    for i in range(10):
        my_save_data.write_text(f"{i}\n")
        if i % 2 == 0:
            (my_save_data.parent / ".boop").touch()
            (my_save_data.parent / ".beep").unlink(missing_ok=True)
        else:
            (my_save_data.parent / ".boop").unlink()
            (my_save_data.parent / ".beep").touch()
        backup.create_backup(my_game_data, None)
        if i % 3 == 0:
            backup.create_backup(my_game_data, "Checkpoint")
    my_save_data.write_text("Sneaky sneaky\n")
    yield my_game_data


class TestRestoreBackup:
    @pytest.mark.parametrize("root_type", ("no_folder", "no_git", "no_manifest"))
    def test_raises_when_theres_no_gsb_repo(self, tmp_path, root_type):
        random_folder = tmp_path / "random folder"
        reference = "blah"
        if root_type != "no_folder":
            random_folder.mkdir()
        if root_type == "no_manifest":
            _git.init(random_folder)
            (random_folder / ".something").touch()
            _git.add(random_folder, ".something")
            commit = _git.commit(random_folder, "placeholder")
            reference = commit.hash
        with pytest.raises(OSError):
            rewind.restore_backup(random_folder, reference)

    def test_raises_when_revision_is_invalid(self, repo):
        with pytest.raises(ValueError):
            rewind.restore_backup(repo, "not-a-thing")

    def test_restores_file_content_to_a_previous_tag(self, repo):
        rewind.restore_backup(repo, "gsb2023.07.13")
        assert (repo / "save" / "data.txt").read_text() == "6\n"

    def test_restores_file_content_to_a_previous_commit(self, repo):
        commit_two = list(history.get_history(repo, tagged_only=False))[-4]
        assert not commit_two["identifier"].startswith("gsb")  # not a tag
        rewind.restore_backup(repo, commit_two["identifier"])
        assert (repo / "save" / "data.txt").read_text() == "2\n"

    def test_restores_a_deleted_file(self, repo):
        assert not (repo / "save" / ".boop").exists()
        rewind.restore_backup(repo, "gsb2023.07.13")
        assert (repo / "save" / ".boop").exists()

    def test_deletes_a_new_file(self, repo):
        assert (repo / "save" / ".beep").exists()
        rewind.restore_backup(repo, "gsb2023.07.13")
        assert not (repo / "save" / ".beep").exists()

    def test_unstaged_changes_are_commited_before_restore(self, repo):
        last_backup = next(iter(history.get_history(repo, tagged_only=False)))
        assert (repo / "save" / "data.txt").read_text() == "Sneaky sneaky\n"
        rewind.restore_backup(repo, last_backup["identifier"])
        assert (repo / "save" / "data.txt").read_text() == "9\n"
        all_backups = list(history.get_history(repo, tagged_only=False))

        assert all_backups[2] == last_backup  # because reverse-chronological

        pre_restore_backup = all_backups[1]

        rewind.restore_backup(repo, pre_restore_backup["identifier"])
        assert (repo / "save" / "data.txt").read_text() == "Sneaky sneaky\n"

    def test_restored_state_gets_backed_up(self, repo):
        rewind.restore_backup(repo, "gsb2023.07.10")

        with pytest.raises(ValueError, match="othing to"):
            _git.add(repo, ["saves"])
            _git.commit(repo, "Test")

        assert (
            "restore"
            in next(iter(history.get_history(repo, tagged_only=False)))[
                "description"
            ].lower()
        )


class TestCLI:
    def test_no_args_initiates_prompt_in_cwd(self, repo):
        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="q\n".encode()
        )

        assert (
            "Select one by number or revision"
            in result.stderr.decode().strip().splitlines()[-2]
        )

    def test_passing_in_a_custom_root(self, repo):
        result = subprocess.run(
            ["gsb", "rewind", "--path", repo.name],
            cwd=repo.parent,
            capture_output=True,
            input="q\n".encode(),
        )

        assert (
            "Select one by number or revision"
            in result.stderr.decode().strip().splitlines()[-2]
        )

    def test_restoring_to_tag_by_argument(self, repo):
        _ = subprocess.run(
            ["gsb", "rewind", "gsb2023.07.12"], cwd=repo, capture_output=True
        )

        assert (repo / "save" / "data.txt").read_text() == "3\n"

    @pytest.mark.parametrize("how", ("short", "full"))
    def test_restoring_to_commit(self, repo, how):
        some_commit = list(_git.log(repo))[-4].hash
        if how == "short":
            some_commit = some_commit[:8]

        _ = subprocess.run(
            ["gsb", "rewind", some_commit],
            cwd=repo,
            capture_output=True,
        )

        assert (repo / "save" / "data.txt").read_text() == "2\n"

    @pytest.mark.parametrize("how", ("by_tag", "by_index"))
    def test_restoring_by_prompt(self, repo, how):
        if how == "by_tag":
            choice = "gsb2023.07.13"
        else:
            choice = "2"

        _ = subprocess.run(
            ["gsb", "rewind"],
            cwd=repo,
            capture_output=True,
            input=f"{choice}\n".encode(),
        )

        assert (repo / "save" / "data.txt").read_text() == "6\n"

    @pytest.mark.parametrize("how", ("by_argument", "by_prompt"))
    def test_unknown_revision_raises_error(self, repo, how):
        args = ["gsb", "rewind"]
        answers = [""]
        if how == "by_argument":
            args.append("not_a_thing")
        else:
            answers.insert(0, "not_a_thing")

        result = subprocess.run(
            args,
            cwd=repo,
            capture_output=True,
            input="\n".join(answers).encode(),
        )

        assert result.returncode == 1
        assert "Could not find" in result.stderr.decode().strip().splitlines()[-1]

    def test_running_on_repo_with_no_tags_retrieves_gsb_commits(self, tmp_path):
        """Like, I guess if the user deleted the initial backup"""
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)
        _git.add(repo, [something.name])
        hash = _git.commit(repo, "Hello").hash[:8]

        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        assert f"1. {hash}" in result.stderr.decode().strip().splitlines()[1]

    def test_running_on_non_gsb_prompts_with_git_commits(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)
        _git.add(repo, [something.name])
        hash = _git.commit(repo, "Hello", _committer=("Testy", "Testy")).hash[:8]

        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        log_lines = result.stderr.decode().strip().splitlines()

        assert "No gsb revisions found" in log_lines[1]
        assert f"1. {hash}" in log_lines[2]

    def test_running_on_empty_repo_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)

        result = subprocess.run(["gsb", "rewind"], cwd=repo, capture_output=True)
        assert result.returncode == 1
        assert "No revisions found" in result.stderr.decode().strip().splitlines()[-1]
