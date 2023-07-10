"""Common fixtures for use across the test package"""
import datetime as dt
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
