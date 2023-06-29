"""Tests for reviewing repo histories"""
import datetime as dt

import pytest

from gsb import _git, history


class TestGetHistory:
    @pytest.fixture
    def repo_with_history(self, tmp_path):
        root = tmp_path / "fossil record"
        root.mkdir()
        _git.init(root)

        _git.commit(root, "First commit", _committer=("you-ser", "me@computer"))
        _git.tag(root, "Init", None, _tagger=("you-ser", "me@computer"))

        (root / "species").write_text("trilobite\n")
        _git.add(root, "species")
        _git.commit(root, "Add an animal", _committer=("you-ser", "me@computer"))

        with (root / "species").open("a") as f:
            f.write("hallucigenia\n")

        _git.add(root, "species")
        _git.commit(root, "I think I'm drunk", _committer=("you-ser", "me@computer"))
        _git.tag(
            root,
            "0.1",
            "Cambrian period",
            _tagger=("you-ser", "me@computer"),
        )

        (root / "species").write_text("trilobite\n")
        _git.add(root, "species")
        _git.commit(root, "Remove hallucigenia", _committer=("you-ser", "me@computer"))
        _git.tag(
            root,
            "0.2",
            "Hello Permian period",
            _tagger=("you-ser", "me@computer"),
        )

        (root / "species").unlink()
        _git.add(root, "species")
        _git.commit(
            root, "Oh no! Everyone's dead!", _committer=("you-ser", "me@computer")
        )

        _git.add(root, "species")
        _git.commit(root, "Started tracking with gsb")
        _git.tag(root, "gsb1.0", "Start of gsb tracking")

        (root / "species").write_text(
            "\n".join(("ichthyosaurs", "archosaurs", "plesiosaurs", "therapsids"))
            + "\n"
        )

        _git.add(root, "species")
        _git.commit(root, "Autocommit")
        _git.tag(root, "gsb1.1", "Triassic")

        (root / "species").write_text("plesiosaurs\n")
        _git.add(root, "species")
        jurassic = _git.commit(root, "Autocommit")

        (root / "species").write_text(
            "\n".join(("sauropods", "therapods", "plesiosaurs", "pterosaurs", "squids"))
            + "\n"
        )

        _git.add(root, "species")
        _git.commit(root, "Autocommit")
        _git.tag(root, "gsb1.2", "Jurassic")

        (root / "species").write_text(
            "\n".join(
                (
                    "sauropods",
                    "therapods",
                    "raptors",
                    "pliosaurs",
                    "plesiosaurs",
                    "mosasaurs",
                    "pterosaurs",
                )
            )
            + "\n"
        )

        _git.add(root, "species")
        _git.commit(root, "Autocommit")

        with (root / "species").open("a") as f:
            f.write("mammals\n")

        _git.add(root, "species")
        _git.commit(root, "It's my ancestors!", _committer=("you-ser", "me@computer"))

        with (root / "species").open("a") as f:
            f.write("\n".join(("birds", "insects", "shark", "squids")) + "\n")

        _git.add(root, "species")
        _git.commit(root, "Autocommit")

        _git.tag(root, "gsb1.3", "Cretaceous (my gracious!)")

        yield root, dt.datetime.fromtimestamp(jurassic.commit_time)

    @pytest.fixture
    def root(self, repo_with_history):
        yield repo_with_history[0]

    @pytest.fixture
    def jurassic_timestamp(self, repo_with_history):
        yield repo_with_history[1]

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
            "Start of gsb tracking",
            "Triassic",
            "Autocommit",
            "Jurassic",
            "Autocommit",
            "Cretaceous",
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
            "0.1",
            "Init",
        ]

    def test_get_history_can_return_non_gsb_commits_as_well(self, root):
        assert [
            revision["description"]
            for revision in history.get_history(
                root, tagged_only=False, include_non_gsb=True, limit=2
            )
        ] == [
            "Cretaceous",
            "It's my ancestors!",
        ]
