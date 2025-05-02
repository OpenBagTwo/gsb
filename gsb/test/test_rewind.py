"""Tests for restoring backups"""

import subprocess
import time

import pytest

from gsb import _git, backup, onboard, rewind
from gsb.history import get_history
from gsb.manifest import MANIFEST_NAME


@pytest.fixture
def repo(tmp_path, patch_tag_naming):
    my_game_data = tmp_path / "best game ever"
    my_save_data = my_game_data / "save" / "data.txt"
    my_save_data.parent.mkdir(parents=True)
    my_save_data.touch()
    _git.init(my_game_data)
    _git.add(my_game_data, my_save_data.name)
    _git.commit(
        my_game_data,
        "Back when the world was new",
        _committer=("Old Man", "old@man"),
    )
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

    def test_restore_tag_references_the_restored_version(self, repo):
        rewind.restore_backup(repo, "gsb2023.07.10")
        assert (
            get_history(repo, limit=1)[0]["identifier"]
            == "gsb2023.07.16.restore_of_gsb2023.07.10"
        )

    def test_restores_file_content_to_a_previous_commit(self, repo):
        commit_two = get_history(repo, tagged_only=False)[-4]
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
        last_backup = get_history(repo, tagged_only=False, limit=1)[0]
        assert (repo / "save" / "data.txt").read_text() == "Sneaky sneaky\n"
        rewind.restore_backup(repo, last_backup["identifier"])
        assert (repo / "save" / "data.txt").read_text() == "9\n"
        all_backups = get_history(repo, tagged_only=False)

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
            in next(iter(get_history(repo, tagged_only=False)))["description"].lower()
        )

    def test_gsb_manifest_and_gitignore_are_not_rewound(self, repo):
        with (repo / ".gitignore").open("a") as ignore:
            ignore.write("nothingtosee\n")
        with (repo / MANIFEST_NAME).open("a") as manifest:
            manifest.write("# it's a comment\n")

        rewind.restore_backup(repo, "gsb2023.07.10")

        with pytest.raises(ValueError, match="othing to"):
            _git.add(repo, ["saves"])
            _git.commit(repo, "Test")

        assert "nothingtosee" in (repo / ".gitignore").read_text().splitlines()
        assert "# it's a comment" in (repo / MANIFEST_NAME).read_text().splitlines()

    def test_gsb_manifest_and_gitignore_can_be_rewound(self, repo):
        with (repo / ".gitignore").open("a") as ignore:
            ignore.write("nothingtosee\n")
        with (repo / MANIFEST_NAME).open("a") as manifest:
            manifest.write("# it's a comment\n")

        rewind.restore_backup(repo, "gsb2023.07.10", keep_gsb_files=False)

        with pytest.raises(ValueError, match="othing to"):
            _git.add(repo, ["saves"])
            _git.commit(repo, "Test")

        assert "nothingtosee" not in (repo / ".gitignore").read_text()
        assert "# it's a comment" not in (repo / MANIFEST_NAME).read_text()

    def test_can_rewind_to_pre_gsb_state(self, repo):
        first_commit = get_history(repo, tagged_only=False, include_non_gsb=True)[-1]

        rewind.restore_backup(repo, first_commit["identifier"])

        assert (repo / MANIFEST_NAME).exists()

    def test_rewind_tag_naming_doesnt_cause_conflicts(self, tmp_path):
        repo_root = tmp_path / "repossess"
        repo_root.mkdir()
        onboard.create_repo(repo_root, "furniture")
        restore_point = get_history(repo_root, limit=1)[0]
        (repo_root / "furniture").mkdir()
        (repo_root / "furniture" / "sofa").write_text("I'm the king!")
        backup.create_backup(repo_root)
        time.sleep(1)  # blergh
        rewind.restore_backup(repo_root, restore_point["identifier"])
        assert not (repo_root / "furniture" / "sofa").exists()

    def test_hard_rewind_does_not_keep_unsaved_changes(self, repo):

        old_history = get_history(repo, tagged_only=False)
        rewind.restore_backup(repo, old_history[0]["identifier"], hard=True)
        new_history = get_history(repo, tagged_only=False)

        assert (repo / "save" / "data.txt").read_text() == "9\n"
        assert new_history == old_history

    def test_hard_rewind_deletes_untracked_files(self, repo):
        restore_point = backup.create_backup(repo)

        (repo / "save" / "fluffy.txt").write_text("doc\n")

        rewind.restore_backup(repo, restore_point, hard=True)

        assert not (repo / "save" / "fluffy.txt").exists()

    def test_hard_rewind_does_not_promote_untagged_backups(self, repo):
        backup.create_backup(repo)

        old_head = get_history(repo, tagged_only=False, limit=1)[0]
        rewind.restore_backup(repo, old_head["identifier"], hard=True)
        new_head = get_history(repo, tagged_only=False, limit=1)[0]

        assert new_head == old_head

    @pytest.mark.parametrize("keep_gsb_files", (True, False))
    def test_hard_rewind_keeps_committed_gsb_file_changes_by_default(
        self, repo, keep_gsb_files
    ):
        kwargs = {"hard": True}
        if not keep_gsb_files:
            kwargs["keep_gsb_files"] = keep_gsb_files

        old_history = get_history(repo, tagged_only=False)

        with (repo / ".gitignore").open("a") as gitignore_file:
            gitignore_file.write("\nboop\n")

        _git.add(repo, (".gitignore",))
        _git.commit(repo, "Not even a GSB backup")

        rewind.restore_backup(repo, old_history[0]["identifier"], **kwargs)
        new_history = get_history(repo, tagged_only=False)

        assert (
            (repo / ".gitignore").read_text().splitlines()[-1] == "boop"
        ) == keep_gsb_files
        if keep_gsb_files:
            assert new_history[1:] == old_history
        else:
            assert new_history == old_history

    def test_hard_rewinding_to_older_backups(self, repo):
        old_history = [
            revision["commit_hash"] for revision in get_history(repo, tagged_only=False)
        ]
        rewind.restore_backup(repo, old_history[5], hard=True)
        new_history = [
            revision["commit_hash"] for revision in get_history(repo, tagged_only=False)
        ]

        assert new_history == old_history[5:]


class TestCLI:
    def test_no_args_initiates_prompt_in_cwd(self, repo):
        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="q\n".encode()
        )

        assert (
            "Select one by number or identifier"
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
            "Select one by number or identifier"
            in result.stderr.decode().strip().splitlines()[-2]
        )

    def test_restoring_to_tag_by_argument(self, repo):
        _ = subprocess.run(
            ["gsb", "rewind", "gsb2023.07.12"], cwd=repo, capture_output=True
        )

        assert (repo / "save" / "data.txt").read_text() == "3\n"

    @pytest.mark.parametrize("how", ("short", "full"))
    def test_restoring_to_commit(self, repo, how):
        some_commit = list(_git.log(repo))[-5].hash
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

    @pytest.mark.parametrize("is_gsb", (True, False), ids=("gsb", "non-gsb"))
    def test_most_recent_backup_is_a_choice(self, repo, is_gsb):
        if is_gsb:
            commit_hash = backup.create_backup(repo)
        else:
            _git.add(repo, ("save",))
            commit_hash = _git.commit(
                repo, "Sneakier and Sneakier", _committer=("you-ser", "me@computer")
            ).hash

        (repo / "save" / "data.txt").write_text("Unsaved changes!\n")

        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="0\n".encode()
        )

        assert f"0. {commit_hash[:8]}" in result.stderr.decode()

        # check that the contents were restored
        assert (repo / "save" / "data.txt").read_text() == "Sneaky sneaky\n"

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
        commit_hash = _git.commit(repo, "Hello").hash[:8]

        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        assert f"1. {commit_hash}" in result.stderr.decode().strip().splitlines()[1]

    def test_running_on_non_gsb_prompts_with_git_commits(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)
        _git.add(repo, [something.name])
        commit_hash = _git.commit(repo, "Hello", _committer=("Testy", "Testy")).hash[:8]

        result = subprocess.run(
            ["gsb", "rewind"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        log_lines = result.stderr.decode().strip().splitlines()

        assert "No GSB revisions found" in log_lines[1]
        assert f"1. {commit_hash}" in log_lines[2]

    def test_running_on_empty_repo_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        something = repo / "file"
        something.touch()
        _git.init(repo)

        result = subprocess.run(["gsb", "rewind"], cwd=repo, capture_output=True)
        assert result.returncode == 1
        assert "No revisions found" in result.stderr.decode().strip().splitlines()[-1]

    def test_force_rewind_of_required_files(self, repo):
        with (repo / MANIFEST_NAME).open("a") as manifest:
            manifest.write("# it's a comment\n")

        _ = subprocess.run(
            ["gsb", "rewind", "gsb2023.07.12", "--include-gsb-settings"],
            cwd=repo,
            capture_output=False,
        )

        assert "# it's a comment" not in (repo / MANIFEST_NAME).read_text()

    def test_hard_rewind_defaults_to_last_backup(self, repo):
        old_history = get_history(repo, tagged_only=False)

        result = subprocess.run(
            ["gsb", "rewind", "--hard"],
            cwd=repo,
            capture_output=False,
            input="y\n".encode(),
        )
        assert result.returncode == 0

        new_history = get_history(repo, tagged_only=False)

        assert (repo / "save" / "data.txt").read_text() == "9\n"
        assert new_history == old_history

    def test_hard_rewind_warns_about_discarding_changes(self, repo):
        result = subprocess.run(
            ["gsb", "rewind", "--hard"],
            cwd=repo,
            capture_output=True,
            input="n\n".encode(),
        )
        assert "any unsaved change" in result.stderr.decode()

        assert (repo / "save" / "data.txt").read_text() == "Sneaky sneaky\n"

    def test_hard_rewind_warns_about_the_backups_youre_deleting(self, repo):
        result = subprocess.run(
            ["gsb", "rewind", "--hard", "gsb2023.07.12"],
            cwd=repo,
            capture_output=True,
            input="n\n".encode(),
        )

        assert "gsb2023.07.13" in result.stderr.decode()
        assert "gsb2023.07.12" not in result.stderr.decode()

    def test_delete_original(self, repo):
        backup.create_backup(repo, tag_message="Saving any unsaved changes")
        old_history = [
            revision["identifier"] for revision in get_history(repo, tagged_only=False)
        ]

        result = subprocess.run(
            ["gsb", "rewind", "gsb2023.07.12", "--delete-original"],
            cwd=repo,
            capture_output=True,
        )

        assert result.returncode == 0

        new_history = []
        for revision in get_history(repo, tagged_only=False):
            if revision["tagged"]:
                new_history.append(revision["identifier"])
            elif "rebase of" in revision["description"]:
                new_history.append(revision["description"].split(" ")[-1][:8])
            else:
                new_history.append(revision["identifier"])

        assert (
            new_history[1:]
            == old_history[: old_history.index("gsb2023.07.12")]
            + old_history[old_history.index("gsb2023.07.12") + 1 :]
        )

    def test_delete_original_is_incompatible_with_hard(self, repo):
        result = subprocess.run(
            ["gsb", "rewind", "--hard", "gsb2023.07.12", "--delete-original"],
            cwd=repo,
            capture_output=True,
            input="n\n".encode(),
        )
        assert result.returncode != 0
        assert (repo / "save" / "data.txt").read_text() == "Sneaky sneaky\n"
