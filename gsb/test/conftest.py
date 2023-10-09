"""Common fixtures for use across the test package"""
import datetime as dt
import shutil
import time
from typing import Generator

import pytest

from gsb import _git, backup, history
from gsb.manifest import MANIFEST_NAME, Manifest


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

    monkeypatch.setattr(backup, "generate_tag_name", mock_tag_namer)


@pytest.fixture(scope="session")
def _repo_with_history(tmp_path_factory):
    root = tmp_path_factory.mktemp("saves") / "fossil record"
    root.mkdir()
    _git._repo(root, new=True, initial_branch="main")

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

    Manifest(root, ("species",)).write()
    (root / ".gitignore").touch()
    _git.add(root, ["species", MANIFEST_NAME, ".gitignore"])
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
        f.write("\n".join(("birds", "insects", "sharks", "squids")) + "\n")

    _git.add(root, ["species"])
    _git.commit(root, "Autocommit")

    _git.tag(root, "gsb1.3", "Cretaceous (my gracious!)")

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
    _git.add(root, ("continents",))
    _git.force_add(root, (MANIFEST_NAME,))
    _git.commit(root, "Autocommit")

    # these contents are new since the last commit
    (root / "oceans").write_text(
        "\n".join(
            (
                "pacific",
                "tethys",
            )
        )
        + "\n"
    )

    yield root, jurassic.timestamp


@pytest.fixture
def root(_repo_with_history, tmp_path):
    """Because the repo-with-history setup is so expensive, we want to perform our
    tests (some of which may rewrite the history) on a copy"""
    destination = tmp_path / "cloney"
    shutil.copytree(_repo_with_history[0], destination)
    yield destination


@pytest.fixture(scope="session")
def jurassic_timestamp(_repo_with_history):
    yield _repo_with_history[1]


@pytest.fixture(scope="session")
def all_backups(_repo_with_history):
    yield history.get_history(
        _repo_with_history[0], tagged_only=False, include_non_gsb=True
    )
