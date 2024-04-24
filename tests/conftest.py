import os

import pyoncatqt.configuration
import pytest


@pytest.fixture(autouse=True)
def _config_path(monkeypatch: pytest.fixture) -> None:
    monkeypatch.setattr(pyoncatqt.configuration, "CONFIG_PATH_FILE", "tests/data/configuration.ini")


@pytest.fixture(autouse=True)
def _get_login(monkeypatch: pytest.fixture) -> None:
    monkeypatch.setattr(os, "getlogin", lambda: "test")


@pytest.fixture()
def token_path() -> str:
    return "tests/data/token.json"
