import json
import os
import threading
from typing import Any, Callable, Dict

import pyoncat
from qtpy.QtCore import QObject, QThread, Signal, Slot
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyoncatqt.configuration import get_data

# Scopes requested for the interactive human-user session.
ONCAT_SCOPES = ["api:read"]


class BackgroundCall(QObject):
    """Runs one callable on a worker thread and reports the outcome.

    PyONCat's device-authorization ``login()`` blocks while it polls the IdP,
    so it must not run on the GUI thread. This worker is moved onto a
    :class:`~qtpy.QtCore.QThread`, runs the callable, and reports back through
    queued signals.

    Attributes
    ----------
    succeeded : Signal(object)
        Emitted with the callable's return value on success.
    failed : Signal(object)
        Emitted with the raised exception on failure.
    finished : Signal
        Emitted once the callable returns, whether or not it succeeded.
    """

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self: QObject, work: Callable[[], object]) -> None:
        super().__init__()
        self._work = work

    @Slot()
    def run(self: QObject) -> None:
        """Run the callable and emit the outcome."""
        try:
            result = self._work()
        except Exception as error:  # noqa: BLE001
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class ChallengeRelay(QObject):
    """Hops the device-authorization challenge from the worker thread to the GUI.

    PyONCat invokes ``verification_handler`` inline on the worker thread while
    ``login()`` is mid-poll. This relay is wired as that handler: it emits a
    queued Qt signal so the dialog is built on the GUI thread, then returns at
    once so polling resumes.

    Attributes
    ----------
    show_verification : Signal(object)
        Emitted with the :class:`pyoncat.DeviceAuthorizationChallenge`.
    """

    show_verification = Signal(object)

    def __call__(self: QObject, challenge: "pyoncat.DeviceAuthorizationChallenge") -> None:
        self.show_verification.emit(challenge)


class VerificationDialog(QDialog):
    """Sign-in dialog showing a clickable link, the user code, and Cancel.

    The user approves the sign-in in a browser using ORNL credentials; this
    dialog only surfaces the verification link and one-time code produced by
    the Device Authorization Grant.

    Params
    ------
    link : str
        The verification URL to open in a browser.
    user_code : str
        The one-time code to enter at the verification URL, if prompted.
    parent : QWidget, optional
        The parent widget.

    Attributes
    ----------
    cancelled : Signal
        Emitted when the user dismisses the dialog before sign-in resolves.
    """

    cancelled = Signal()

    def __init__(self: QDialog, link: str, user_code: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sign in to ONCat")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Open this link in your browser to approve the sign-in:"))
        link_label = QLabel(f'<a href="{link}">{link}</a>')
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)
        layout.addWidget(QLabel(f"If asked for a code, enter:  {user_code}"))

        self._resolved = False
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.close)
        layout.addWidget(self.button_cancel)

    def resolve(self: QDialog) -> None:
        """Mark the sign-in resolved so a programmatic close is not a cancel.

        The owner calls this before closing the dialog once sign-in succeeds,
        so the close does not read as a user cancellation.
        """
        self._resolved = True

    def closeEvent(self: QDialog, event: QCloseEvent) -> None:
        """Route Cancel and the window frame to the cancel signal.

        Dismissing the dialog any way sets the cancel event rather than
        leaving the worker polling.
        """
        if not self._resolved:
            self.cancelled.emit()
        super().closeEvent(event)


class ONCatLogin(QGroupBox):
    """
    ONCatLogin widget for connecting to the ONCat service.

    This widget provides a status label and a button that starts an
    interactive, browser-based sign-in using PyONCat's Device Authorization
    Grant. When a sign-in is started, a :class:`VerificationDialog` shows a
    link the user opens to approve the sign-in with ORNL credentials.

    Params
    ------
    client_id : str, optional
        The client_id is an ONCat client ID. Defaults to None. client_id is required or key is required
    key : str, optional
        The key used to retrieve ONCat client ID from configuration. Defaults to None.
    parent : QWidget, optional
        The parent widget.
    timeout : float, optional
        Request timeout, in seconds, for the ONCat agent. Defaults to 10.0.
    kwargs : Dict[str, Any], optional
        Additional keyword arguments. ``login_title`` overrides the sign-in
        dialog window title.

    Attributes
    ----------
    connection_updated : Signal
        Signal emitted when the connection status is updated.

    Methods
    -------
    update_connection_status() -> None:
        Update the connection status.
    is_connected() -> bool:
        Check if connected to OnCat.
    get_agent_instance() -> pyoncat.ONCat:
        Get the OnCat agent instance.
    connect_to_oncat() -> None:
        Start an interactive sign-in to OnCat.
    read_token() -> dict:
        Read token from file.
    write_token(token: dict) -> None:
        Write token to file.
    """

    connection_updated = Signal(bool)

    def __init__(
        self: QGroupBox,
        *,
        client_id: str = None,
        key: str = None,
        parent: QWidget = None,
        timeout: float = 10.0,
        **kwargs: Dict[str, Any],
    ) -> None:
        """
        Initialize the ONCatLogin widget.

        Params
        ------
        client_id : str, optional
            The client_id is an ONCat client ID. Defaults to None.
        key : str, optional
            The key used to retrieve ONCat client ID from configuration. Defaults to None.
        parent : QWidget, optional
            The parent widget.
        timeout : float, optional
            Request timeout, in seconds, for the ONCat agent. Defaults to 10.0.
        **kwargs : Dict[str, Any], optional
            Additional keyword arguments. ``login_title`` overrides the sign-in
            dialog window title.
        """
        super().__init__(parent)
        self._login_title = kwargs.pop("login_title", "Sign in to ONCat")

        self.oncat_options_layout = QGridLayout()
        self.setLayout(self.oncat_options_layout)  # Set the layout for the group box

        # Status indicator (disconnected: red, connected: green)
        self.status_label = QLabel("")
        self.status_label.setToolTip("ONCat connection status.")
        self.oncat_options_layout.addWidget(self.status_label, 4, 0)

        # Connect to OnCat button
        self.oncat_button = QPushButton("&Connect to ONCat")
        self.oncat_button.setFixedWidth(300)
        self.oncat_button.setToolTip("Connect to ONCat (requires login credentials).")
        self.oncat_button.clicked.connect(self.connect_to_oncat)
        self.oncat_options_layout.addWidget(self.oncat_button, 4, 1)

        # Log out of OnCat button
        self.logout_button = QPushButton("&Log out of ONCat")
        self.logout_button.setFixedWidth(300)
        self.logout_button.setToolTip("Log out of ONCat and revoke the current session.")
        self.logout_button.clicked.connect(self.disconnect_from_oncat)
        self.oncat_options_layout.addWidget(self.logout_button, 5, 1)

        self.timeout = timeout

        self.oncat_url = get_data("login.oncat", "oncat_url")
        if client_id is not None:
            self.client_id = client_id
        elif key is not None:
            self.client_id = get_data("login.oncat", f"{key}_id")
        else:
            raise ValueError(f"Invalid module {key}. No OnCat client Id is found or provided for this application.")

        # use the partial client id to generate the filename
        token_filename = f"{self.client_id[0:8]}_token.json"
        if key:
            token_filename = f"{key}_token.json"
        self.token_path = os.path.abspath(f"{os.path.expanduser('~')}/.pyoncatqt/{token_filename}")

        # Relay the device-authorization challenge from the worker thread to
        # the GUI thread, where the verification dialog is built.
        self._relay = ChallengeRelay()
        self._relay.show_verification.connect(self._show_verification)

        self.agent = pyoncat.ONCat(
            self.oncat_url,
            client_id=self.client_id,
            flow=pyoncat.DEVICE_AUTHORIZATION_FLOW,
            scopes=ONCAT_SCOPES,
            # Pass in token getter/setter callbacks here:
            token_getter=self.read_token,
            token_setter=self.write_token,
            # Raise InteractionRequiredError on a dead session instead of
            # silently re-prompting from inside a data call.
            reauth_on_expired=pyoncat.REAUTH_INTERACTION_REQUIRED,
            verification_handler=self._relay,
            timeout=self.timeout,
        )

        # Keep the running thread/worker referenced so Qt does not GC them.
        self._thread: QThread = None
        self._worker: BackgroundCall = None
        self.login_dialog: VerificationDialog = None
        self._cancel_event: threading.Event = None

        self.update_connection_status()

    def update_connection_status(self: QGroupBox) -> None:
        """Update connection status"""
        connected = self.is_connected
        if connected:
            self.status_label.setText("ONCat: Connected")
            self.status_label.setStyleSheet("color: green")
        else:
            self.status_label.setText("ONCat: Disconnected")
            self.status_label.setStyleSheet("color: red")
        # Only allow connecting while disconnected and logging out while
        # there is a live session to act on.
        self.oncat_button.setEnabled(not connected)
        self.logout_button.setEnabled(connected)
        self.connection_updated.emit(connected)

    @property
    def is_connected(self: QGroupBox) -> bool:
        """
        Check if connected to OnCat.

        Returns
        -------
        bool
            True if connected, False otherwise.
        """

        # Without a stored token there is no session to probe, and calling a
        # data method would drive login() into a blocking, interactive Device
        # Authorization Grant on the GUI thread. Report "not connected"
        # without any network round trip.
        if not self.agent.has_stored_token():
            return False

        try:
            self.agent.Facility.list()
            return True
        except pyoncat.InvalidRefreshTokenError:
            return False
        except pyoncat.InteractionRequiredError:
            return False
        except pyoncat.LoginRequiredError:
            return False
        except Exception:  # noqa BLE001
            return False

    def get_agent_instance(self: QGroupBox) -> pyoncat.ONCat:
        """
        Get OnCat agent instance.

        Returns
        -------
        pyoncat.ONCat
            The OnCat agent instance.
        """
        return self.agent

    def connect_to_oncat(self: QGroupBox) -> None:
        """Start an interactive, browser-based sign-in to OnCat.

        Sign-in runs on a worker thread while PyONCat polls the IdP; a
        :class:`VerificationDialog` surfaces the approval link. The connection
        status is refreshed once sign-in resolves.
        """
        # Ignore repeat clicks while a sign-in is already in progress.
        if self._thread is not None:
            return

        # A still-valid stored session needs no interactive sign-in.
        if self.is_connected:
            self.update_connection_status()
            return

        # Otherwise discard any stale token first. The Device Authorization
        # Grant's login() returns immediately when a token is already stored --
        # even an expired one -- so without this the browser challenge would
        # never appear and the click would seem to do nothing.
        self._clear_stored_token()

        self.oncat_button.setEnabled(False)
        self.status_label.setText("ONCat: Starting sign-in...")
        self._cancel_event = threading.Event()
        self._run_in_background(
            lambda: self.agent.login(cancel_event=self._cancel_event),
            self._on_sign_in_ok,
            self._on_sign_in_error,
        )

    def disconnect_from_oncat(self: QGroupBox) -> None:
        """Log out of OnCat, revoking the current session.

        ``logout()`` revokes the refresh token server-side rather than only
        clearing it locally, so it does network I/O and must run on a worker
        thread. The connection status is refreshed once it resolves.
        """
        # Ignore repeat clicks while another job is already in progress.
        if self._thread is not None:
            return

        self.logout_button.setEnabled(False)
        self.oncat_button.setEnabled(False)
        self.status_label.setText("ONCat: Logging out...")
        self._run_in_background(
            self.agent.logout,
            self._on_logout_ok,
            self._on_logout_error,
        )

    def _on_logout_ok(self: QGroupBox, _: object) -> None:
        """Finish a successful logout and refresh the connection status."""
        self._clear_stored_token()
        self.update_connection_status()

    def _on_logout_error(self: QGroupBox, error: BaseException) -> None:
        """Report a failed server-side logout and refresh the status.

        The local token is cleared regardless, so this session is unusable
        here; surface the server-side revocation failure rather than claim a
        clean logout.
        """
        self._clear_stored_token()
        QMessageBox.warning(
            self,
            "ONCat",
            f"Logged out on this device, but ONCat could not revoke the session server-side:\n{error}",
        )
        self.update_connection_status()

    def _run_in_background(
        self: QGroupBox,
        work: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Run ``work`` on a worker thread, routing the outcome to callbacks."""
        self._thread = QThread()
        self._worker = BackgroundCall(work)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(on_success)
        self._worker.failed.connect(on_error)
        # Drop the references only after the thread has fully stopped, so
        # nothing is collected mid-run.
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_job)
        self._thread.start()

    def _clear_job(self: QGroupBox) -> None:
        self._thread = None
        self._worker = None

    @Slot(object)
    def _show_verification(self: QGroupBox, challenge: "pyoncat.DeviceAuthorizationChallenge") -> None:
        """Build and show the verification dialog on the GUI thread."""
        self.status_label.setText("ONCat: Waiting for browser approval...")
        link = challenge.verification_uri_complete or challenge.verification_uri
        self.login_dialog = VerificationDialog(link, challenge.user_code, parent=self)
        self.login_dialog.setWindowTitle(self._login_title)
        self.login_dialog.cancelled.connect(self._on_cancel_requested)
        self.login_dialog.show()

    @Slot()
    def _on_cancel_requested(self: QGroupBox) -> None:
        """Signal the worker to abort the poll loop."""
        if self._cancel_event is not None:
            self._cancel_event.set()
        self.status_label.setText("ONCat: Cancelling sign-in...")

    def _on_sign_in_ok(self: QGroupBox, _: object) -> None:
        """Finish a successful sign-in and refresh the connection status."""
        self._close_dialog()
        self._cancel_event = None
        self.update_connection_status()

    def _on_sign_in_error(self: QGroupBox, error: BaseException) -> None:
        """Report a failed or cancelled sign-in and refresh the status."""
        self._close_dialog()
        self._cancel_event = None
        if not isinstance(error, pyoncat.DeviceAuthorizationCancelled):
            QMessageBox.warning(self, "ONCat", str(error))
        self.update_connection_status()

    def _close_dialog(self: QGroupBox) -> None:
        """Close the verification dialog without treating it as a cancel."""
        if self.login_dialog is not None:
            self.login_dialog.resolve()
            self.login_dialog.close()
            self.login_dialog = None

    def _clear_stored_token(self: QGroupBox) -> None:
        """Remove any persisted token so the next login() re-prompts.

        The Device Authorization Grant's login() returns immediately when a
        token is already stored, even if it is expired, so a stale token has
        to be cleared for the browser challenge to appear.
        """
        if os.path.exists(self.token_path):
            os.remove(self.token_path)

    def read_token(self: QGroupBox) -> dict:
        """
        Read token from file.

        Returns
        -------
        dict
            The token dictionary.
        """
        # If there is not a token stored, return None
        if not os.path.exists(self.token_path):
            return None

        with open(self.token_path, encoding="UTF-8") as storage:
            try:
                return json.load(storage)
            except json.JSONDecodeError:
                return None

    def write_token(self: QGroupBox, token: dict) -> None:
        """
        Write token to file.

        Params
        ------
        token : dict
            The token dictionary.
        """
        # Check if directory exists
        if not os.path.exists(os.path.dirname(self.token_path)):
            os.makedirs(os.path.dirname(self.token_path))
        # Write token to file
        with open(self.token_path, "w", encoding="UTF-8") as storage:
            json.dump(token, storage)
        # Change permissions to read-only by user
        os.chmod(self.token_path, 0o600)
