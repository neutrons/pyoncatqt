.. _sample:

Sample Usage
============

ONCatLogin Widget
-----------------
The following is a simple example of how to use the ONCatLogin widget in a PyQt application.
This example creates a main window with an ONCatLogin widget and two QListWidgets to display
the instrument lists for the SNS and HFIR facilities. The instrument lists are updated when
the connection status changes.
The only required argument for the ``ONCatLogin`` widget is the client ID. The client ID is a unique identifier
for the application that is used to authenticate with the ONCat server. The client ID is provided by the ONCat support team.
and should exist in pyoncatqt configuration file.

.. code:: python

    from pyoncatqt.login import ONCatLogin
    from qtpy.QtWidgets import QApplication, QLabel, QListWidget, QVBoxLayout, QWidget

    class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Create and add the Oncat widget
        self.oncat_widget = ONCatLogin(key="", parent=self)
        self.oncat_widget.connection_updated.connect(self.update_instrument_lists)
        layout.addWidget(self.oncat_widget)

        # Add list widgets for the instrument lists
        self.sns_list = QListWidget()
        self.hfir_list = QListWidget()

        layout.addWidget(QLabel("SNS Instruments:"))
        layout.addWidget(self.sns_list)
        layout.addWidget(QLabel("HFIR Instruments:"))
        layout.addWidget(self.hfir_list)

        self.setLayout(layout)
        self.setWindowTitle("ONCat Application")
        self.oncat_widget.update_connection_status()

    def update_instrument_lists(self, is_connected):
        """Update the contents of the instrument lists based on the connection status."""
        self.sns_list.clear()
        self.hfir_list.clear()

        if is_connected:
            sns_instruments = self.oncat_widget.agent.Instrument.list(facility="SNS")
            hfir_instruments = self.oncat_widget.agent.Instrument.list(facility="HFIR")

            for instrument in sns_instruments:
                self.sns_list.addItem(instrument.get("name"))

            for instrument in hfir_instruments:
                self.hfir_list.addItem(instrument.get("name"))

    if __name__ == "__main__":
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())


ONCatLoginDialog
----------------

The `ONCatLoginDialog` can be imported and used separate from the `ONCatLogin` widget to give developers
the ability to customize the login process. In order to use the `ONCatLoginDialog`, you must have an
instance of the `pyoncat.ONCat` agent.
If you chose to use the `ONCatLogin` widget instead, the agent is already created for you.
The `ONCatLoginDialog` requires the agent to be passed in as an argument.
The agent is used to authenticate the user and manage the connection to the ONCat server.
At a minimum the agent must be initialized with the ONCat server URL, flow, and the client ID.
Additional callbacks can be passed in to handle token storage and retrieval. These would be simple functions to read and write
the token to a JSON file.

.. code:: python

    import pyoncat

    # This is a temporary "client ID" intended for use in this tutorial **only**.
    # For your own work, please contact ONCat Support to be issued your own credentials.
    CLIENT_ID = "c0686270-e983-4c71-bd0e-bfa47243a47f"

    # We will use the testing version of ONCat for this sample.
    ONCAT_URL = "https://oncat-testing.ornl.gov"

    oncat = pyoncat.ONCat(
        ONCAT_URL,
        client_id=CLIENT_ID,
        flow=pyoncat.RESOURCE_OWNER_CREDENTIALS_FLOW,
    )

The following example demonstrates how to use the `ONCatLoginDialog` in a PyQt application.

- The application consists of a single button labeled "Login to ONCat".
- When the button is clicked, it triggers the opening of the `ONCatLoginDialog`,
  allowing the user to input their ONCat login credentials securely.
- Upon successful login, the dialog closes, and the application can proceed with its functionality,
  utilizing the authenticated ONCat connection for data management tasks.

.. code:: python

    from pyoncatqt.login import ONCatLoginDialog
    import pyoncat
    from qtpy.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget
    import sys

    class MainWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.initUI()

        def initUI(self):
            layout = QVBoxLayout()

            # Create a button to open the ONCat login dialog
            self.login_button = QPushButton("Login to ONCat")
            self.login_button.clicked.connect(self.open_oncat_login_dialog)
            layout.addWidget(self.login_button)
            self.setLayout(layout)
            self.setWindowTitle("ONCat Login Example")

            # Create an instance of the pyoncat agent pyoncat.ONCat
            CLIENT_ID = "c0686270-e983-4c71-bd0e-bfa47243a47f"

            ONCAT_URL = "https://oncat-testing.ornl.gov"

            self.agent = pyoncat.ONCat(
                ONCAT_URL,
                client_id=CLIENT_ID,
                flow=pyoncat.RESOURCE_OWNER_CREDENTIALS_FLOW,
            )

        def open_oncat_login_dialog(self):
            dialog = ONCatLoginDialog(agent=self.agent, parent=self)
            dialog.exec_()

    if __name__ == "__main__":
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
