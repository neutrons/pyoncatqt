import functools
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import oauthlib
import pyoncat
import pyoncatqt.configuration
import pytest
from pyoncatqt.configuration import get_data
from pyoncatqt.login import ONCatLogin, ONCatLoginDialog
from qtpy import QtCore
from qtpy.QtWidgets import QApplication, QDialog, QErrorMessage, QLineEdit, QPushButton


@pytest.fixture()
def _config_path(monkeypatch):
    monkeypatch.setattr(pyoncatqt.configuration, "CONFIG_PATH_FILE", "tests/data/configuration.ini")


@pytest.fixture()
def token_path():
    return "tests/data/token.json"


def check_status(login_status):
    print("here")
    assert login_status


def test_login_dialog_creation():
    application = QApplication([])
    dialog = ONCatLoginDialog(application)
    assert isinstance(dialog, QDialog)
    assert dialog.windowTitle() == "Use U/XCAM to connect to OnCat"
    assert isinstance(dialog.user_name, QLineEdit)
    assert dialog.user_name.text() == os.getlogin()
    assert isinstance(dialog.user_pwd, QLineEdit)
    assert dialog.user_pwd.echoMode() == QLineEdit.Password
    assert isinstance(dialog.button_login, QPushButton)
    assert isinstance(dialog.button_cancel, QPushButton)


def test_login(qtbot, _config_path):  # noqa ARG001
    dialog = ONCatLogin(key="test")
    dialog.login_dialog = ONCatLoginDialog(agent=MagicMock(), parent=dialog)
    dialog.login_dialog.login_status.connect(check_status)
    qtbot.addWidget(dialog)
    dialog.show()

    completed = False

    def handle_dialog():
        nonlocal completed

        qtbot.keyClicks(dialog.login_dialog.user_pwd, "password")
        qtbot.wait(2000)
        qtbot.mouseClick(dialog.login_dialog.button_login, QtCore.Qt.LeftButton)
        completed = True

    def dialog_completed():
        nonlocal completed
        assert completed is True

    QtCore.QTimer.singleShot(500, functools.partial(handle_dialog))
    qtbot.mouseClick(dialog.oncat_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(dialog_completed, timeout=5000)


def test_login_dialog_nominal(qtbot):
    agent = MagicMock()
    dialog = ONCatLoginDialog(agent=agent)
    dialog.login_status.connect(check_status)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyClicks(dialog.user_pwd, "password")
    qtbot.wait(2000)
    assert dialog.user_pwd.text() == "password"
    qtbot.mouseClick(dialog.button_login, QtCore.Qt.LeftButton)
    assert agent.login.called_once_with(os.getlogin(), "password")


def test_login_dialog_no_password(qtbot):
    mock_agent = MagicMock(spec=pyoncat.ONCat)
    mock_agent.login.side_effect = pyoncat.LoginRequiredError
    dialog = ONCatLoginDialog(agent=mock_agent)
    dialog.show_message = MagicMock()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(2000)
    assert dialog.user_pwd.text() == ""
    qtbot.mouseClick(dialog.button_login, QtCore.Qt.LeftButton)
    assert mock_agent.login.called_once_with(os.getlogin(), "")
    assert dialog.show_message.called_once_with("A username and/or password was not provided when logging in.")


def test_login_dialog_bad_password(qtbot):
    mock_agent = MagicMock(spec=pyoncat.ONCat)
    mock_agent.login.side_effect = oauthlib.oauth2.rfc6749.errors.InvalidGrantError
    dialog = ONCatLoginDialog(agent=mock_agent)
    dialog.show_message = MagicMock()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyClicks(dialog.user_pwd, "bad_password")
    qtbot.wait(2000)
    assert dialog.user_pwd.text() == "bad_password"
    qtbot.mouseClick(dialog.button_login, QtCore.Qt.LeftButton)
    assert mock_agent.login.called_once_with(os.getlogin(), "bad_password")
    assert dialog.show_message.called_once_with("Invalid username or password. Please try again.")


def test_login_dialog_no_agent(qtbot):
    with patch("pyoncatqt.login.ONCatLoginDialog.show_message"):
        dialog = ONCatLoginDialog()
        qtbot.addWidget(dialog)
        assert dialog.show_message.called_once_with("No Agent provided for login.")


def test_login_read_token(qtbot, _config_path, token_path):  # noqa ARG001
    widget = ONCatLogin(key="test")
    qtbot.addWidget(widget)
    widget.token_path = token_path
    test_token = widget.read_token()
    with open(token_path, "r") as f:
        actual_token = json.load(f)
    assert test_token == actual_token


def test_write_token(qtbot, _config_path, token_path):  # noqa ARG001
    widget = ONCatLogin(key="test")
    qtbot.addWidget(widget)
    widget.token_path = token_path
    with open(token_path, "r") as f:
        actual_token = json.load(f)
    widget.write_token(actual_token)
    with open(token_path, "r") as f:
        assert f.read() == json.dumps(actual_token)