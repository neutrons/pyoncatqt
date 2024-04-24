"""Test the garnet.garnet.gui function

This is the entry point for the GUI application.
"""

import sys
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from pyoncatqt._version import __version__
from pyoncatqt.pyoncatqt import MainWindow, PyONCatQt, gui
from PyQt5.QtWidgets import QMainWindow


def test_gui_version() -> None:
    """Test the version flag."""
    t_argv = sys.argv.copy()
    sys.argv.append("--version")
    with pytest.raises(SystemExit) as excinfo:
        gui()
    assert excinfo.value.code is None
    sys.argv = t_argv


@patch("pyoncatqt.pyoncatqt.QApplication")
@patch("pyoncatqt.pyoncatqt.PyONCatQt")
def test_gui(mock_pyoncatqt: mock, mock_qtapp: mock) -> None:
    """Test the GUI entry point."""
    with pytest.raises(SystemExit) as excinfo:
        gui()

    assert excinfo.type == SystemExit
    assert mock_pyoncatqt.called
    assert mock_qtapp.called


def test_PyONCatQt_initialization(qtbot: pytest.fixture) -> None:
    pyoncatqt = PyONCatQt()
    qtbot.addWidget(pyoncatqt)

    assert pyoncatqt.windowTitle() == f"PYONCATQT - {__version__}"

    assert isinstance(pyoncatqt.centralWidget(), MainWindow)
    qtbot.wait(500)
