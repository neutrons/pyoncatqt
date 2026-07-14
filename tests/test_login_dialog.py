import json
import os
import threading
from unittest.mock import MagicMock, patch

import pyoncat
import pytest
from qtpy.QtWidgets import QDialog, QPushButton

from pyoncatqt.login import (
    BackgroundCall,
    ChallengeRelay,
    ONCatLogin,
    VerificationDialog,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_widget(qtbot):
    w = ONCatLogin(key="test")
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# BackgroundCall
# ---------------------------------------------------------------------------


def test_background_call_success(qtbot):
    results, errors, finished = [], [], []
    worker = BackgroundCall(lambda: 42)
    worker.succeeded.connect(results.append)
    worker.failed.connect(errors.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.run()
    assert results == [42]
    assert errors == []
    assert finished == [True]


def test_background_call_failure(qtbot):
    err = RuntimeError("boom")

    def bad():
        raise err

    worker = BackgroundCall(bad)
    errors, finished = [], []
    worker.failed.connect(errors.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.run()
    assert errors == [err]
    assert finished == [True]


# ---------------------------------------------------------------------------
# ChallengeRelay
# ---------------------------------------------------------------------------


def test_challenge_relay_emits_signal(qtbot):
    relay = ChallengeRelay()
    challenge = MagicMock()
    received = []
    relay.show_verification.connect(received.append)
    relay(challenge)
    assert received == [challenge]


# ---------------------------------------------------------------------------
# VerificationDialog
# ---------------------------------------------------------------------------


def test_verification_dialog_creation(qtbot):
    dialog = VerificationDialog("https://example.com/auth?code=ABCD", "ABCD-1234")
    qtbot.addWidget(dialog)
    assert isinstance(dialog, QDialog)
    assert dialog.windowTitle() == "Sign in to ONCat"
    assert isinstance(dialog.button_cancel, QPushButton)


def test_verification_dialog_cancel_emits_signal(qtbot):
    dialog = VerificationDialog("https://example.com", "XYZW")
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.cancelled, timeout=1000):
        dialog.close()


def test_verification_dialog_resolve_suppresses_cancel(qtbot):
    dialog = VerificationDialog("https://example.com", "XYZW")
    qtbot.addWidget(dialog)
    emitted = []
    dialog.cancelled.connect(lambda: emitted.append(True))
    dialog.resolve()
    dialog.close()
    qtbot.wait(100)
    assert emitted == []


# ---------------------------------------------------------------------------
# ONCatLogin constructor
# ---------------------------------------------------------------------------


def test_login_key(qtbot):
    widget = ONCatLogin(key="test")
    qtbot.addWidget(widget)
    assert widget.client_id == "0123456489"
    assert widget.token_path.endswith("test_token.json")
    assert widget.agent is not None


def test_login_client_id(qtbot):
    client_id = "12cnfjejsfsdf3456789ab"
    widget = ONCatLogin(client_id=client_id)
    qtbot.addWidget(widget)
    assert widget.client_id == client_id
    assert widget.token_path.endswith(f"{client_id[0:8]}_token.json")


def test_login_client_id_key(qtbot):
    client_id = "12cnfjejsfsdf3456789ab"
    key = "test"
    widget = ONCatLogin(client_id=client_id, key=key)
    qtbot.addWidget(widget)
    assert widget.client_id == client_id
    assert widget.token_path.endswith(f"{key}_token.json")


# ---------------------------------------------------------------------------
# get_agent_instance
# ---------------------------------------------------------------------------


def test_get_agent(qtbot):
    widget = _make_widget(qtbot)
    mock_agent = MagicMock()
    widget.agent = mock_agent
    assert widget.get_agent_instance() is mock_agent


# ---------------------------------------------------------------------------
# is_connected
# ---------------------------------------------------------------------------


def test_is_connected_no_token(qtbot):
    """No stored token: return False without any network call."""
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = False
    w.agent = mock_agent
    assert w.is_connected is False
    mock_agent.Facility.list.assert_not_called()


def test_is_connected_success(qtbot):
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = True
    mock_agent.Facility.list.return_value = []
    w.agent = mock_agent
    assert w.is_connected is True


def test_is_connected_invalid_refresh(qtbot):
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = True
    mock_agent.Facility.list.side_effect = pyoncat.InvalidRefreshTokenError
    w.agent = mock_agent
    assert w.is_connected is False


def test_is_connected_interaction_required(qtbot):
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = True
    mock_agent.Facility.list.side_effect = pyoncat.InteractionRequiredError
    w.agent = mock_agent
    assert w.is_connected is False


def test_is_connected_login_required(qtbot):
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = True
    mock_agent.Facility.list.side_effect = pyoncat.LoginRequiredError
    w.agent = mock_agent
    assert w.is_connected is False


def test_is_connected_other_exception(qtbot):
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = True
    mock_agent.Facility.list.side_effect = RuntimeError("unexpected")
    w.agent = mock_agent
    assert w.is_connected is False


# ---------------------------------------------------------------------------
# connect_to_oncat
# ---------------------------------------------------------------------------


def test_connect_to_oncat_already_connected(qtbot):
    """A working session skips sign-in and refreshes status."""
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = True
    mock_agent.Facility.list.return_value = []
    w.agent = mock_agent

    w.connect_to_oncat()

    assert w._thread is None
    mock_agent.login.assert_not_called()
    assert "Connected" in w.status_label.text()


def test_connect_to_oncat_starts_sign_in(qtbot):
    """Not connected: background job is started with agent.login and a cancel_event.

    _run_in_background is patched so the work and callbacks can be driven
    synchronously, avoiding the PySide6 deleteLater race in QThread cleanup.
    """
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = False
    w.agent = mock_agent

    calls = []
    with patch.object(w, "_run_in_background", side_effect=lambda *a: calls.append(a)):
        w.connect_to_oncat()

    assert w.oncat_button.isEnabled() is False
    assert len(calls) == 1

    work, on_success, _on_error = calls[0]

    # work is the lambda passed to login — call it and check the cancel_event arg
    work()
    _, kwargs = mock_agent.login.call_args
    assert isinstance(kwargs.get("cancel_event"), threading.Event)

    # calling on_success simulates the thread completing successfully
    on_success(None)
    assert w.oncat_button.isEnabled() is True


def test_connect_to_oncat_in_progress_ignored(qtbot):
    """A second click while a sign-in is running is a no-op."""
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    w.agent = mock_agent
    w._thread = MagicMock()  # simulate a sign-in already running

    w.connect_to_oncat()

    mock_agent.has_stored_token.assert_not_called()
    mock_agent.login.assert_not_called()


def test_connect_to_oncat_clears_stale_token(qtbot, tmp_path):
    """A stale token file is removed before the device flow starts.

    _clear_stored_token is called synchronously in connect_to_oncat before
    the background thread launches, so we patch _run_in_background to avoid
    starting a real thread and test only the token-clearing behaviour.
    """
    w = _make_widget(qtbot)
    token_file = tmp_path / "stale_token.json"
    token_file.write_text('{"access_token": "dead"}')
    w.token_path = str(token_file)

    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = False
    w.agent = mock_agent

    with patch.object(w, "_run_in_background"):
        w.connect_to_oncat()

    assert not token_file.exists()


# ---------------------------------------------------------------------------
# _show_verification
# ---------------------------------------------------------------------------


def test_show_verification(qtbot):
    w = _make_widget(qtbot)
    challenge = MagicMock()
    challenge.verification_uri = "https://example.com/auth"
    challenge.verification_uri_complete = "https://example.com/auth?user_code=ABCD"
    challenge.user_code = "ABCD"

    w._show_verification(challenge)

    assert isinstance(w.login_dialog, VerificationDialog)
    assert "Waiting" in w.status_label.text()

    w.login_dialog.resolve()
    w.login_dialog.close()
    w.login_dialog = None


# ---------------------------------------------------------------------------
# _on_cancel_requested
# ---------------------------------------------------------------------------


def test_on_cancel_requested(qtbot):
    w = _make_widget(qtbot)
    cancel_event = threading.Event()
    w._cancel_event = cancel_event

    w._on_cancel_requested()

    assert cancel_event.is_set()
    assert "Cancelling" in w.status_label.text()


# ---------------------------------------------------------------------------
# _on_sign_in_error
# ---------------------------------------------------------------------------


def test_on_sign_in_error_cancelled(qtbot):
    """DeviceAuthorizationCancelled does not show a warning dialog."""
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = False
    w.agent = mock_agent
    w.oncat_button.setEnabled(False)

    with patch("pyoncatqt.login.QMessageBox.warning") as mock_warn:
        w._on_sign_in_error(pyoncat.DeviceAuthorizationCancelled("cancelled"))
        mock_warn.assert_not_called()

    assert w.oncat_button.isEnabled() is True


def test_on_sign_in_error_shows_messagebox(qtbot):
    """Any other error shows a QMessageBox warning with the error text."""
    w = _make_widget(qtbot)
    mock_agent = MagicMock()
    mock_agent.has_stored_token.return_value = False
    w.agent = mock_agent
    w.oncat_button.setEnabled(False)

    with patch("pyoncatqt.login.QMessageBox.warning") as mock_warn:
        w._on_sign_in_error(RuntimeError("connection failed"))

    mock_warn.assert_called_once()
    assert "connection failed" in mock_warn.call_args[0][2]
    assert w.oncat_button.isEnabled() is True


# ---------------------------------------------------------------------------
# Token persistence
# ---------------------------------------------------------------------------


def test_read_token(qtbot, token_path):
    widget = _make_widget(qtbot)
    widget.token_path = token_path
    test_token = widget.read_token()
    with open(token_path, "r") as f:
        actual_token = json.load(f)
    assert test_token == actual_token


def test_write_token(qtbot, token_path):
    widget = _make_widget(qtbot)
    widget.token_path = token_path
    with open(token_path, "r") as f:
        actual_token = json.load(f)
    widget.write_token(actual_token)
    with open(token_path, "r") as f:
        assert f.read() == json.dumps(actual_token)


def test_clear_stored_token(qtbot, tmp_path):
    widget = _make_widget(qtbot)
    token_file = tmp_path / "token.json"
    token_file.write_text('{"access_token": "abc"}')
    widget.token_path = str(token_file)
    widget._clear_stored_token()
    assert not token_file.exists()


def test_clear_stored_token_no_file(qtbot, tmp_path):
    """Calling _clear_stored_token when no file exists does not raise."""
    widget = _make_widget(qtbot)
    widget.token_path = str(tmp_path / "nonexistent.json")
    widget._clear_stored_token()
