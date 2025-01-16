import functools
import json
import os
from unittest.mock import MagicMock, patch

import oauthlib
import pyoncat
import pytest
from pyoncatqt.configuration import get_data
from pyoncatqt.login import ONCatLogin, ONCatLoginDialog
from qtpy import QtCore
from qtpy.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton


def check_status(login_status: bool) -> None:
    assert login_status


def test_login_dialog_creation() -> None:
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


def test_login_key(qtbot: pytest.fixture) -> None:
    dialog = ONCatLogin(key="test")
    dialog.login_dialog = ONCatLoginDialog(agent=MagicMock(), parent=dialog)
    dialog.login_dialog.login_status.connect(check_status)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.client_id == "0123456489"
    assert dialog.token_path.endswith("test_token.json")

    completed = False

    def handle_dialog() -> None:
        nonlocal completed

        qtbot.keyClicks(dialog.login_dialog.user_pwd, "password")
        qtbot.wait(2000)
        qtbot.mouseClick(dialog.login_dialog.button_login, QtCore.Qt.LeftButton)
        completed = True

    def dialog_completed() -> None:
        nonlocal completed
        assert completed is True

    QtCore.QTimer.singleShot(500, functools.partial(handle_dialog))
    qtbot.mouseClick(dialog.oncat_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(dialog_completed, timeout=5000)


def test_login_client_id(qtbot: pytest.fixture) -> None:
    client_id = "12cnfjejsfsdf3456789ab"
    dialog = ONCatLogin(client_id=client_id)
    dialog.login_dialog = ONCatLoginDialog(agent=MagicMock(), parent=dialog)
    dialog.login_dialog.login_status.connect(check_status)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.client_id == client_id
    # token_12cnf.json
    assert dialog.token_path.endswith(f"{client_id[0:8]}_token.json")
    completed = False

    def handle_dialog() -> None:
        nonlocal completed

        qtbot.keyClicks(dialog.login_dialog.user_pwd, "password")
        qtbot.wait(2000)
        qtbot.mouseClick(dialog.login_dialog.button_login, QtCore.Qt.LeftButton)
        completed = True

    def dialog_completed() -> None:
        nonlocal completed
        assert completed is True

    QtCore.QTimer.singleShot(500, functools.partial(handle_dialog))
    qtbot.mouseClick(dialog.oncat_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(dialog_completed, timeout=5000)


def test_login_client_id_key(qtbot: pytest.fixture) -> None:
    client_id = "12cnfjejsfsdf3456789ab"
    key = "test"

    dialog = ONCatLogin(client_id=client_id, key=key)
    dialog.login_dialog = ONCatLoginDialog(agent=MagicMock(), parent=dialog)
    dialog.login_dialog.login_status.connect(check_status)
    qtbot.addWidget(dialog)
    dialog.show()

    # client id provided as parameter
    assert dialog.client_id == client_id
    # key used for filename only token_shiver.json
    assert dialog.token_path.endswith(f"{key}_token.json")
    completed = False

    def handle_dialog() -> None:
        nonlocal completed

        qtbot.keyClicks(dialog.login_dialog.user_pwd, "password")
        qtbot.wait(2000)
        qtbot.mouseClick(dialog.login_dialog.button_login, QtCore.Qt.LeftButton)
        completed = True

    def dialog_completed() -> None:
        nonlocal completed
        assert completed is True

    QtCore.QTimer.singleShot(500, functools.partial(handle_dialog))
    qtbot.mouseClick(dialog.oncat_button, QtCore.Qt.LeftButton)

    qtbot.waitUntil(dialog_completed, timeout=5000)


def test_get_agent() -> None:
    dialog = ONCatLogin(key="test")
    dialog.agent = MagicMock()
    assert dialog.get_agent_instance() == dialog.agent


def test_is_connected() -> None:
    dialog = ONCatLogin(key="test")
    mock_agent = MagicMock()
    dialog.agent = mock_agent
    mock_agent.Instrument.list.return_value = [{"name": "Instrument1"}, {"name": "Instrument2"}]
    dialog.login_dialog = MagicMock()

    assert dialog.is_connected
    dialog.connect_to_oncat()
    assert not dialog.login_dialog.exec_.called


def test_login_dialog_nominal(qtbot: pytest.fixture) -> None:
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


def test_login_dialog_no_password(qtbot: pytest.fixture) -> None:
    mock_agent = MagicMock(spec=pyoncat.ONCat)
    mock_agent.login.side_effect = pyoncat.LoginRequiredError
    dialog = ONCatLoginDialog(agent=mock_agent)
    dialog.show_message = MagicMock()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(2000)
    assert dialog.user_pwd.text() == ""
    assert dialog.button_login.isEnabled() is False
    qtbot.mouseClick(dialog.button_login, QtCore.Qt.LeftButton)
    assert mock_agent.login.called_once_with(os.getlogin(), "")
    assert dialog.show_message.called_once_with("A username and/or password was not provided when logging in.")


def test_login_dialog_bad_password(qtbot: pytest.fixture) -> None:
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


def test_login_dialog_no_agent(qtbot: pytest.fixture) -> None:
    with patch("pyoncatqt.login.ONCatLoginDialog.show_message"):
        dialog = ONCatLoginDialog()
        qtbot.addWidget(dialog)
        assert dialog.show_message.called_once_with("No Agent provided for login.")


def test_read_token(qtbot: pytest.fixture, token_path: pytest.fixture) -> None:
    widget = ONCatLogin(key="test")
    qtbot.addWidget(widget)
    widget.token_path = token_path
    test_token = widget.read_token()
    with open(token_path, "r") as f:
        actual_token = json.load(f)
    assert test_token == actual_token


def test_write_token(qtbot: pytest.fixture, token_path: pytest.fixture) -> None:
    widget = ONCatLogin(key="test")
    qtbot.addWidget(widget)
    widget.token_path = token_path
    with open(token_path, "r") as f:
        actual_token = json.load(f)
    widget.write_token(actual_token)
    with open(token_path, "r") as f:
        assert f.read() == json.dumps(actual_token)
