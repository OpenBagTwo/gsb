"""Tests for exporting standalone backups"""
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from gsb import _git, export
from gsb.manifest import Manifest


class TestExportBackup:
    @pytest.fixture(autouse=True)
    def put_autogenned_files_in_tmp(self, root, monkeypatch) -> None:
        original_archive_method = _git.archive

        def patched_archive(
            repo_root: Path, filename: Path, reference: str = "HEAD"
        ) -> None:
            if not filename.is_absolute():
                filename = root.parent / filename
            return original_archive_method(repo_root, filename, reference)

        monkeypatch.setattr(_git, "archive", patched_archive)

    def test_exporting_a_backup(self, root):
        export.export_backup(root, "gsb1.2")
        assert len(list(root.parent.glob("history of life_gsb1.2.*"))) == 1

    def test_exporting_a_backup_with_a_specific_filename(self, root, tmp_path):
        export.export_backup(root, "0.2", tmp_path / "exported.tbz")
        assert (tmp_path / "exported.tbz").exists()

    @pytest.mark.parametrize(
        "path_provided", (False, True), ids=("autogenned", "provided")
    )
    def test_exporting_will_not_overwrite_existing_file(
        self, root, tmp_path, path_provided
    ):
        (root.parent / "history of life_gsb1.0.zip").touch()
        (root.parent / "history of life_gsb1.0.tar.gz").touch()
        (tmp_path / "exported.tar.xz").touch()

        with pytest.raises(FileExistsError, match="already exists"):
            export.export_backup(
                root, "gsb1.0", tmp_path / "exported.tar.xz" if path_provided else None
            )

    def test_writing_zip_archive(self, root, tmp_path):
        export.export_backup(root, "gsb1.1", tmp_path / "exported.zip")
        with zipfile.ZipFile(tmp_path / "exported.zip") as archive:
            assert archive.read("species").decode("utf-8").startswith("ichthyosaurs\n")

    @pytest.mark.parametrize("compression", (None, "gz", "bz2", "xz"))
    def test_writing_tar_archive(self, root, tmp_path, compression, all_backups):
        archive_path = tmp_path / "exported.tar"
        if compression:
            archive_path = archive_path.with_suffix(f".tar.{compression}")

        export.export_backup(root, all_backups[0]["commit_hash"], archive_path)
        with tarfile.open(archive_path, f'r:{compression or ""}') as archive:
            assert archive.extractfile("continents").read().decode(
                "utf-8"
            ).strip().splitlines() == [
                "laurasia",
                "gondwana",
            ]

    def test_no_extension_raises_value_error(self, root, tmp_path):
        with pytest.raises(ValueError, match="does not specify an extension"):
            export.export_backup(root, "gsb1.2", tmp_path / "archive")

    def test_unknown_extension_raises_not_implemented_error(self, root, tmp_path):
        with pytest.raises(NotImplementedError):
            export.export_backup(
                root, "gsb1.2", tmp_path / "archive.tar.proprietaryext"
            )

    def test_repo_name_is_sanitized(self, tmp_path, root):
        repo = tmp_path / "diabolical"
        repo.mkdir()
        Manifest(repo, "I\\'m / soo ?evil?", ("doot",)).write()
        (repo / "doot").touch()
        _git.init(repo)
        _git.add(repo, (".gsb_manifest", "doot"))
        commit = _git.commit(repo, "Blahblah")
        export.export_backup(repo, commit.hash[:8])
        assert len(list(root.parent.glob(f"*evil*{commit.hash[:8]}.*"))) == 1


class TestCLI:
    def test_no_args_initiates_prompt_in_cwd(self, root):
        result = subprocess.run(
            ["gsb", "export"], cwd=root, capture_output=True, input="q\n".encode()
        )

        assert (
            "Select one by number or identifier"
            in result.stderr.decode().strip().splitlines()[-2]
        )

    def test_passing_in_a_custom_root(self, root):
        result = subprocess.run(
            ["gsb", "export", "--path", root.name],
            cwd=root.parent,
            capture_output=True,
            input="q\n".encode(),
        )

        assert (
            "Select one by number or identifier"
            in result.stderr.decode().strip().splitlines()[-2]
        )

    @pytest.mark.parametrize("how", ("arg", "prompt", "index"))
    def test_exporting_a_tag_by(self, root, how) -> None:
        args = ["gsb1.1"] if how == "arg" else []
        if how == "prompt":
            script: bytes | None = "gsb1.1\n".encode()
        elif how == "index":
            script = "3\n".encode()
        else:  # how == "arg"
            script = None

        _ = subprocess.run(
            ["gsb", "export", *args], cwd=root, capture_output=True, input=script
        )

        assert len(list(root.glob("history of life_gsb1.1.*"))) == 1

    @pytest.mark.parametrize("how", ("short", "full", "prompt"))
    def test_exporting_a_commit_by_(self, root, all_backups, how):
        assert not all_backups[0]["tagged"]
        some_commit = all_backups[0]["commit_hash"]

        if how != "full":
            some_commit = some_commit[:8]

        args = [some_commit] if how != "prompt" else []
        script = None if how != "prompt" else "0\n".encode()

        _ = subprocess.run(
            ["gsb", "export", *args],
            cwd=root,
            capture_output=True,
            input=script,
        )

        assert len(list(root.glob(f"history of life_{some_commit}.*"))) == 1

    @pytest.mark.parametrize("how", ("by_argument", "by_prompt"))
    def test_unknown_revision_raises_error(self, root, how):
        args = ["gsb", "export"]
        answers = [""]
        if how == "by_argument":
            args.append("not_a_thing")
        else:
            answers.insert(0, "not_a_thing")

        result = subprocess.run(
            args,
            cwd=root,
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
            ["gsb", "export"], cwd=repo, capture_output=True, input="q\n".encode()
        )
        assert f"1. {commit_hash}" in result.stderr.decode().strip().splitlines()[1]

    def test_specifying_archive_name(self, root):
        subprocess.run(
            ["gsb", "export", "gsb1.0", "-o", "../archive.tar"],
            cwd=root,
            capture_output=True,
        )

        with tarfile.open(root.parent / "archive.tar", "r") as archive:
            assert (
                archive.extractfile(".gitignore").read().decode("utf-8").strip() == ""
            )

    def test_raises_if_archive_name_has_no_extension(self, root):
        result = subprocess.run(
            ["gsb", "export", "gsb1.0", "-o", "../archive"],
            cwd=root,
            capture_output=True,
        )

        assert result.returncode == 1
        assert "extension" in result.stderr.decode().splitlines()[-1]

    @pytest.mark.parametrize("filename", ("provided_filename", "autogen_filename"))
    @pytest.mark.parametrize("how", ("explicit", "short_flag"))
    @pytest.mark.parametrize(
        "archive_format", ("zip", "tar", "tar.gz", "tar.bz2", "tar.xz")
    )
    def test_specifying_an_archive_format(self, root, archive_format, how, filename):
        if how == "explicit":
            args = [f"--format=.{archive_format}"]
        else:
            args = [
                {
                    "zip": "-p",
                    "tar": "-t",
                    "tar.gz": "-z",
                    "tar.bz2": "-j",
                    "tar.xz": "-J",
                }[archive_format]
            ]

        if filename == "provided_filename":
            expected_path = root.parent / f"archive.{archive_format}"
            args.extend(["--output", "../archive"])
        else:
            expected_path = root / f"history of life_gsb1.3.{archive_format}"

        subprocess.run(
            ["gsb", "export", "gsb1.3", *args], cwd=root, capture_output=True
        )

        if archive_format == "zip":
            with zipfile.ZipFile(expected_path) as archive:
                assert (
                    archive.read("species")
                    .decode("utf-8")
                    .strip()
                    .splitlines()[-1]
                    .strip()
                    == "squids"
                )
        else:
            with tarfile.open(expected_path) as archive:
                assert (
                    archive.extractfile("species")
                    .read()
                    .decode("utf-8")
                    .strip()
                    .splitlines()[-1]
                    .strip()
                    == "squids"
                )

    @pytest.mark.parametrize(
        "flags",
        (
            ["-jJ"],
            ["-z", "-t"],
            ["-p", "--format", "zip"],
            pytest.param(
                ["-zz"],
                marks=pytest.mark.xfail(
                    reason="this would be nasty to implement in Click"
                ),
            ),
        ),
        ids=("short_combined", "short_separate", "short_and_long", "repeated_flag"),
    )
    def test_raises_if_multiple_formats_are_specified(self, root, flags):
        result = subprocess.run(
            ["gsb", "export", *flags, "0.2"],
            cwd=root,
            capture_output=True,
        )

        assert result.returncode == 1
        assert "conflicting" in result.stderr.decode().splitlines()[-1].lower()
