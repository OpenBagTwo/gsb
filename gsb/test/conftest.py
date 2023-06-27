"""Common fixtures for use across the test package"""
import pytest

from gsb import _git


@pytest.fixture(autouse=True)
def suppress_git_config(monkeypatch):
    def empty_git_config() -> dict[str, str]:
        return {}

    monkeypatch.setattr(_git, "_git_config", empty_git_config)
