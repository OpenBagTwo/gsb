"""Common fixtures for use across the test package"""
import datetime as dt
import time
from typing import Generator

import pytest

from gsb import _git, backup


@pytest.fixture(autouse=True)
def suppress_git_config(monkeypatch):
    def empty_git_config() -> dict[str, str]:
        return {}

    monkeypatch.setattr(_git, "_git_config", empty_git_config)


@pytest.fixture
def patch_tag_naming(monkeypatch):
    def tag_name_generator() -> Generator[str, None, None]:
        date = dt.date(2023, 7, 10)
        while True:
            yield date.strftime("gsb%Y.%m.%d")
            date += dt.timedelta(days=1)

    tag_namer = tag_name_generator()

    def mock_tag_namer() -> str:
        return next(tag_namer)

    monkeypatch.setattr(backup, "_generate_tag_name", mock_tag_namer)


@pytest.fixture(scope="module")
def _repo_with_history(tmp_path_factory):
    root = tmp_path_factory.mktemp("saves") / "fossil record"
    root.mkdir()
    _git.init(root)

    (root / ".touched").touch()
    _git.add(root, [".touched"])

    _git.commit(root, "First commit", _committer=("you-ser", "me@computer"))
    _git.tag(root, "Init", None, _tagger=("you-ser", "me@computer"))

    (root / "species").write_text("trilobite\n")
    _git.add(root, ["species"])
    _git.commit(root, "Add an animal", _committer=("you-ser", "me@computer"))

    with (root / "species").open("a") as f:
        f.write("hallucigenia\n")

    _git.add(root, ["species"])
    _git.commit(root, "I think I'm drunk", _committer=("you-ser", "me@computer"))
    _git.tag(
        root,
        "0.1",
        "Cambrian period",
        _tagger=("you-ser", "me@computer"),
    )

    (root / "species").write_text("trilobite\n")
    _git.add(root, ["species"])
    _git.commit(root, "Remove hallucigenia", _committer=("you-ser", "me@computer"))
    _git.tag(
        root,
        "0.2",
        "Hello Permian period",
        _tagger=("you-ser", "me@computer"),
    )

    (root / "species").unlink()
    _git.add(root, ["species"])
    _git.commit(root, "Oh no! Everyone's dead!", _committer=("you-ser", "me@computer"))

    (root / ".gsb_manifest").write_text('patterns = ["species"]\n')
    (root / ".gitignore").touch()
    _git.add(root, ["species", ".gsb_manifest", ".gitignore"])
    _git.tag(root, "gsb1.0", "Start of gsb tracking")

    (root / "species").write_text(
        "\n".join(("ichthyosaurs", "archosaurs", "plesiosaurs", "therapsids")) + "\n"
    )

    _git.add(root, ["species"])
    _git.commit(root, "Autocommit")
    _git.tag(root, "gsb1.1", "Triassic")

    time.sleep(1)

    (root / "species").write_text("plesiosaurs\n")
    _git.add(root, ["species"])
    jurassic = _git.commit(root, "Autocommit")

    (root / "species").write_text(
        "\n".join(("sauropods", "therapods", "plesiosaurs", "pterosaurs", "squids"))
        + "\n"
    )

    _git.add(root, ["species"])
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

    _git.add(root, ["species"])
    _git.commit(root, "Autocommit")

    with (root / "species").open("a") as f:
        f.write("mammals\n")

    _git.add(root, ["species"])
    _git.commit(root, "It's my ancestors!", _committer=("you-ser", "me@computer"))

    with (root / "species").open("a") as f:
        f.write("\n".join(("birds", "insects", "shark", "squids")) + "\n")

    _git.add(root, ["species"])
    _git.commit(root, "Autocommit")

    _git.tag(root, "gsb1.3", "Cretaceous (my gracious!)")

    yield root, jurassic.timestamp


@pytest.fixture(scope="module")
def root(_repo_with_history):
    yield _repo_with_history[0]


@pytest.fixture(scope="module")
def jurassic_timestamp(_repo_with_history):
    yield _repo_with_history[1]
