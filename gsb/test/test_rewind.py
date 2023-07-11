"""Tests for restoring backups"""
import pytest

from gsb import _git, backup, history, onboard, rewind


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

    @pytest.fixture
    def repo(self, tmp_path, patch_tag_naming):
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
