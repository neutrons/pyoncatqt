import json
import os
from pathlib import Path

import pytest

import pyoncatqt.configuration


@pytest.fixture(autouse=True)
def _config_path(monkeypatch: pytest.MonkeyPatch) -> None:
    test_dir = os.path.dirname(os.path.abspath(__file__))
    configuration_path = os.path.join(test_dir, "data", "configuration.ini")
    monkeypatch.setattr(pyoncatqt.configuration, "CONFIG_PATH_FILE", configuration_path)


@pytest.fixture(autouse=True)
def _isolate_token_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect ~/.pyoncatqt into a temporary directory.

    ONCatLogin derives its token path from ``os.path.expanduser('~')`` and
    probes the stored session during construction, so without this every
    widget built in the suite would read from and write to the developer's
    real home directory. Pointing ``$HOME`` at ``tmp_path`` keeps token
    storage confined to a per-test temporary location.
    """
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def token_path(tmp_path: Path) -> str:
    """A temporary token file, isolated from the developer filesystem."""
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({"name": "token", "version": "1.0.0", "description": "fake token"}))
    return str(token_file)
