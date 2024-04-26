from unittest.mock import patch

import pytest
from pyoncatqt.version import get_version


@patch("pyoncatqt._version.__version__", "1.0.0")
def test_get_version_existing_version(capsys: patch) -> None:
    """Test get_version when _version module exists"""
    get_version()
    captured = capsys.readouterr()
    assert captured.out.strip() == "pyoncatqt version: 1.0.0"
