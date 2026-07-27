import json
import os
import threading
from typing import Any, Callable, Dict

import pyoncat
import requests
from qtpy.QtCore import QObject, QThread, Signal, Slot
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import (
    QApplication,
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

# Outcomes of probing the stored session. A genuinely dead/expired token
# (NEEDS_LOGIN) must be cleared to trigger a fresh authorization; a transient
# connectivity failure (UNREACHABLE) must leave the token intact so the session
# survives the outage.
_SESSION_CONNECTED = "connected"
_SESSION_NEEDS_LOGIN = "needs_login"
_SESSION_UNREACHABLE = "unreachable"


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
        # The line breaks are explicit rather than word-wrapped: a wrapped label
        # reports its height through heightForWidth, which the dialog does not
        # resolve before it is first shown, so it opens too short to read. Hard
        # breaks give the label an exact size hint in both directions.
        note_label = QLabel(
            "If the webpage to confirm the activation shows your 3\n"
            "character U/XCAMS ID instead of the 8 character unique ID,\n"
            "you should be able to continue and click confirm."
        )
        layout.addWidget(note_label)

        self._resolved = False
        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.clicked.connect(self.reject)
        layout.addWidget(self.button_cancel)

    def resolve(self: QDialog) -> None:
        """Mark the sign-in resolved so a programmatic close is not a cancel.

        The owner calls this before closing the dialog once sign-in succeeds,
        so the close does not read as a user cancellation.
        """
        self._resolved = True

    def reject(self: QDialog) -> None:
        """Route the Cancel button and the Escape key to the cancel signal.

        Qt sends both the Cancel button (wired here) and the Escape key
        through ``reject()``, which dismisses the dialog via ``done()``
        without firing :meth:`closeEvent`. The cancel signal is emitted here
        so those paths do not silently leave the worker polling; the guard
        keeps it from re-emitting after a resolved sign-in or a later close.
        """
        if not self._resolved:
            self._resolved = True
            self.cancelled.emit()
        super().reject()

    def closeEvent(self: QDialog, event: QCloseEvent) -> None:
        """Route the window frame to the cancel signal.

        Dismissing the dialog via the window frame sets the cancel event
        rather than leaving the worker polling.
        """
        if not self._resolved:
            self._resolved = True
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
        # Latched once teardown begins so queued challenges cannot reopen the
        # verification dialog after the widget is on its way out.
        self._closing: bool = False

        # A parent window closing does not deliver a closeEvent to this child
        # widget, so also tear down when the application is shutting down.
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown_background)

        # Cached connection state. Probing ONCat does a blocking network
        # round trip, so it must never run on the GUI thread;
        # update_connection_status renders from this cache, which the worker
        # thread refreshes via _refresh_connection_status and the login/logout
        # callbacks keep in sync.
        self._connected: bool = False

        # Render the initial (disconnected) state, then probe in the
        # background so a still-valid stored session is reflected without
        # blocking the GUI thread during construction.
        self.update_connection_status()
        self._refresh_connection_status()

    def update_connection_status(self: QGroupBox) -> None:
        """Render the cached connection status.

        Reads the cached connection state instead of probing ONCat, so it
        never does network I/O on the GUI thread. The cache is refreshed by
        :meth:`_refresh_connection_status` and by the login/logout callbacks.
        """
        connected = self._connected
        if connected:
            self.status_label.setText("ONCat: Connected")
            self.status_label.setStyleSheet("color: green")
        else:
            self.status_label.setText("ONCat: Disconnected")
            self.status_label.setStyleSheet("color: red")
        # Only allow connecting while disconnected and logging out while
        # there is a live session to act on.
        self.oncat_button.setEnabled(not connected)
        self.logout_button.setEnabled(connected or self.agent.has_stored_token())
        self.connection_updated.emit(connected)

    def _refresh_connection_status(self: QGroupBox) -> None:
        """Probe ONCat on a worker thread and refresh the cached status.

        :attr:`is_connected` does a blocking network round trip, so it is run
        through the worker infrastructure rather than on the GUI thread.
        Without a stored token there is nothing to probe, so the cache is
        cleared without spawning a thread; likewise, no probe is started while
        another job (sign-in or logout) is already running.
        """
        if not self.agent.has_stored_token():
            self._connected = False
            self.update_connection_status()
            return
        if self._thread is not None:
            return
        # Surface a "checking" state and disable both actions while the probe
        # is in flight; _on_probe_done/_on_probe_error restore the label and
        # enabled state via update_connection_status.
        self.oncat_button.setEnabled(False)
        self.logout_button.setEnabled(False)
        self.status_label.setText("ONCat: Checking session...")
        self._run_in_background(
            lambda: self.is_connected,
            self._on_probe_done,
            self._on_probe_error,
        )

    def _on_probe_done(self: QGroupBox, connected: object) -> None:
        """Cache the worker's probe result and refresh the status."""
        self._connected = bool(connected)
        self.update_connection_status()

    def _on_probe_error(self: QGroupBox, _: BaseException) -> None:
        """Treat a failed probe as disconnected and refresh the status."""
        self._connected = False
        self.update_connection_status()

    def _probe_session(self: QGroupBox) -> str:
        """Probe the stored session and classify the outcome.

        Distinguishes a genuinely invalid or expired token -- which must be
        cleared to trigger a fresh authorization -- from a transient
        connectivity failure, during which the token is preserved so the
        session survives the outage rather than forcing a needless re-login.

        Returns
        -------
        str
            One of :data:`_SESSION_CONNECTED`, :data:`_SESSION_NEEDS_LOGIN`, or
            :data:`_SESSION_UNREACHABLE`.
        """
        # Without a stored token there is no session to probe, and calling a
        # data method would drive login() into a blocking, interactive Device
        # Authorization Grant on the GUI thread. Report "needs login" without
        # any network round trip.
        if not self.agent.has_stored_token():
            return _SESSION_NEEDS_LOGIN

        try:
            self.agent.Facility.list()
            return _SESSION_CONNECTED
        except (
            pyoncat.InvalidRefreshTokenError,
            pyoncat.InteractionRequiredError,
            pyoncat.LoginRequiredError,
        ):
            # The token is dead or a fresh interactive sign-in is required.
            return _SESSION_NEEDS_LOGIN
        except (
            pyoncat.DeviceAuthorizationNetworkError,
            requests.exceptions.RequestException,
        ):
            # A transport-layer failure (timeout, DNS, connection refused) is
            # not evidence the token is dead, so keep it and report the outage.
            return _SESSION_UNREACHABLE
        except Exception:  # noqa BLE001
            # An unclassified failure is likewise no proof the token is dead;
            # err on the side of preserving it.
            return _SESSION_UNREACHABLE

    @property
    def is_connected(self: QGroupBox) -> bool:
        """
        Check if connected to OnCat.

        Returns
        -------
        bool
            True if connected, False otherwise.
        """
        return self._probe_session() == _SESSION_CONNECTED

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

        status = self._probe_session()

        # A still-valid stored session needs no interactive sign-in.
        if status == _SESSION_CONNECTED:
            self._connected = True
            self.update_connection_status()
            return

        # A transient connectivity failure is not evidence the stored session
        # is dead. Preserve the token -- clearing it would force a needless
        # re-authorization once the outage clears -- and surface the failure
        # instead of starting an interactive sign-in on a blip.
        if status == _SESSION_UNREACHABLE:
            self.update_connection_status()
            QMessageBox.warning(
                self,
                "ONCat",
                "Could not reach ONCat to verify the session. Your sign-in has "
                "been kept; please check your connection and try again.",
            )
            return

        # Otherwise the token is genuinely invalid or expired: discard it
        # first. The Device Authorization Grant's login() returns immediately
        # when a token is already stored -- even an expired one -- so without
        # this the browser challenge would never appear and the click would
        # seem to do nothing.
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
        self._connected = False
        self.update_connection_status()

    def _on_logout_error(self: QGroupBox, error: BaseException) -> None:
        """Report a failed server-side logout and refresh the status.

        The local token is cleared regardless, so this session is unusable
        here; surface the server-side revocation failure rather than claim a
        clean logout.
        """
        self._clear_stored_token()
        self._connected = False
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

    def closeEvent(self: QGroupBox, event: QCloseEvent) -> None:
        """Stop any in-flight background job before the widget is torn down.

        The worker thread is unparented and its ``succeeded``/``failed``
        signals are wired to bound methods on this widget. If the widget were
        destroyed mid-job, a late-finishing worker could call back into a
        half-destroyed C++ object. Cancel the poll loop where possible, detach
        the outcome callbacks so nothing outlives the widget, then stop and
        wait for the thread.
        """
        self._shutdown_background()
        super().closeEvent(event)

    def _shutdown_background(self: QGroupBox) -> None:
        """Cancel, detach, and join any running background job.

        Complements the normal :meth:`_clear_job` teardown path, which handles
        jobs that finish on their own; this handles the case where the widget
        (or its host window/application) shuts down while a job is still
        running. Idempotent: safe to invoke from both :meth:`closeEvent` and
        the application's ``aboutToQuit`` signal.
        """
        if self._closing:
            return
        # Latch first so a challenge already queued on the GUI thread cannot
        # rebuild the verification dialog once teardown has begun.
        self._closing = True
        # Stop routing any further (or in-flight queued) challenges to the GUI.
        try:
            self._relay.show_verification.disconnect(self._show_verification)
        except (RuntimeError, TypeError):
            pass
        # Close any dialog currently awaiting browser approval; resolve() keeps
        # this teardown close from being read as a user cancellation.
        self._close_dialog()

        thread = self._thread
        if thread is None:
            return
        # Unblock a sign-in poll loop; logout/probe have no cancel hook and
        # simply run to completion (bounded by the agent request timeout).
        if self._cancel_event is not None:
            self._cancel_event.set()
        # Detach the outcome callbacks so a late-finishing job cannot call back
        # into a widget that is being destroyed. The finished chain (quit /
        # deleteLater / _clear_job) is left intact so the thread still cleans
        # itself up.
        worker = self._worker
        if worker is not None:
            try:
                worker.succeeded.disconnect()
                worker.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
        # Stop the event loop and block until the worker has returned.
        thread.quit()
        thread.wait()

    @Slot(object)
    def _show_verification(self: QGroupBox, challenge: "pyoncat.DeviceAuthorizationChallenge") -> None:
        """Build and show the verification dialog on the GUI thread.

        A challenge may still be sitting queued on the GUI thread when teardown
        begins; reject it once closing so a dialog is never reopened on a widget
        that is going away.
        """
        if self._closing:
            return
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
        self._connected = True
        self.update_connection_status()

    def _on_sign_in_error(self: QGroupBox, error: BaseException) -> None:
        """Report a failed or cancelled sign-in and refresh the status."""
        self._close_dialog()
        self._cancel_event = None
        self._connected = False
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
