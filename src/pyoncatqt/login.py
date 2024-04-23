import json
import os
import sys

import oauthlib
import pyoncat
from qtpy.QtCore import QSize, Signal
from qtpy.QtWidgets import (
    QDialog,
    QErrorMessage,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from pyoncatqt.configuration import get_data


class ONCatLoginDialog(QDialog):
    """OnCat login dialog"""

    login_status = Signal(bool)

    def __init__(self, agent=None, parent=None, **kwargs):
        super().__init__(parent)
        username_label_text = kwargs.pop("username_label", "UserId")
        password_label_text = kwargs.pop("password_label", "Password")
        window_title_text = kwargs.pop("login_title", "Use U/XCAM to connect to OnCat")
        pwd_echo = kwargs.pop("password_echo", QLineEdit.Password)

        self.setWindowTitle(window_title_text)

        username_label = QLabel(username_label_text)
        self.user_name = QLineEdit(os.getlogin(), self)

        password_label = QLabel(password_label_text)
        self.user_pwd = QLineEdit(self)
        self.user_pwd.setEchoMode(pwd_echo)

        self.button_login = QPushButton("&Login")
        self.button_cancel = QPushButton("Cancel")

        self.setMinimumSize(QSize(400, 100))
        layout = QVBoxLayout()
        self.setLayout(layout)

        input_layout = QFormLayout()
        input_layout.addRow(username_label, self.user_name)
        input_layout.addRow(password_label, self.user_pwd)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_login)
        button_layout.addWidget(self.button_cancel)

        layout.addLayout(input_layout)
        layout.addLayout(button_layout)

        self.user_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.user_pwd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if agent:
            self.agent = agent
        else:
            self.show_message("No Agent provided for login")
            return

        # connect signals and slots
        self.button_login.clicked.connect(self.accept)
        self.button_cancel.clicked.connect(self.reject)
        self.user_pwd.returnPressed.connect(self.accept)

        self.user_pwd.setFocus()

    def show_message(self, msg):
        """Will show a error dialog with the given message"""
        error = QErrorMessage(self)
        error.showMessage(msg)
        error.exec_()

    def accept(self):
        """Accept"""
        try:
            self.agent.login(
                self.user_name.text(),
                self.user_pwd.text(),
            )
        except oauthlib.oauth2.rfc6749.errors.InvalidGrantError:
            self.show_message("Invalid username or password. Please try again.")
            self.user_pwd.setText("")
            return
        except pyoncat.LoginRequiredError:
            self.show_message("A username and/or password was not provided when logging in.")
            self.user_pwd.setText("")
            return

        self.login_status.emit(True)
        # close dialog
        self.close()


class ONCatLogin(QGroupBox):
    """ONCat widget"""

    connection_updated = Signal(bool)

    def __init__(self, key=None, parent=None, **kwargs):
        super().__init__(parent)
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

        self.error_message_callback = None

        # OnCat agent

        self.oncat_url = get_data("login.oncat", "oncat_url")
        self.client_id = get_data("login.oncat", f"{key}_id")
        if not self.client_id:
            raise ValueError(f"Invalid key: {key}, ONCat client ID not found")
            return

        self.token_path = os.path.abspath(f"{os.path.expanduser('~')}/.pyoncatqt/{key}_token.json")

        self.agent = pyoncat.ONCat(
            self.oncat_url,
            client_id=self.client_id,
            # Pass in token getter/setter callbacks here:
            token_getter=self.read_token,
            token_setter=self.write_token,
            flow=pyoncat.RESOURCE_OWNER_CREDENTIALS_FLOW,
        )

        self.login_dialog = ONCatLoginDialog(agent=self.agent, parent=self, **kwargs)
        self.update_connection_status()

    def update_connection_status(self):
        """Update connection status"""
        if self.is_connected:
            self.status_label.setText("ONCat: Connected")
            self.status_label.setStyleSheet("color: green")
        else:
            self.status_label.setText("ONCat: Disconnected")
            self.status_label.setStyleSheet("color: red")

        self.connection_updated.emit(self.is_connected)

    @property
    def is_connected(self):
        """Check if connected to OnCat"""
        try:
            self.agent.Facility.list()
            return True
        except pyoncat.InvalidRefreshTokenError:
            return False
        except pyoncat.LoginRequiredError:
            return False
        except Exception:  # noqa BLE001
            return False

    def get_agent_instance(self):
        """Get OnCat agent instance"""
        return self.agent

    def connect_to_oncat(self):
        """Connect to OnCat"""
        # Check if already connected to OnCat
        if self.is_connected:
            return

        self.login_dialog.exec_()
        self.update_connection_status()
        # self.parent.update_boxes()

    def read_token(self):
        """Read token from file"""
        # If there is not a token stored, return None
        if not os.path.exists(self.token_path):
            return None

        with open(self.token_path, encoding="UTF-8") as storage:
            return json.load(storage)

    def write_token(self, token):
        """Write token to file"""
        # Check if directory exists
        if not os.path.exists(os.path.dirname(self.token_path)):
            os.makedirs(os.path.dirname(self.token_path))
        # Write token to file
        with open(self.token_path, "w", encoding="UTF-8") as storage:
            json.dump(token, storage)
        # Change permissions to read-only by user
        os.chmod(self.token_path, 0o600)
