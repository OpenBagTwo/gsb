"""Tests for exporting standalone backups"""
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
