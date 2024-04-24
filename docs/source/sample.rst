Sample Usage
============

ONCatLoginDialog
----------------
The following is a simple example of how to This example demonstrates how to
integrate the `ONCatLoginDialog` into a PyQt application.

- The application consists of a single button labeled "Login to ONCat".
- When the button is clicked, it triggers the opening of the `ONCatLoginDialog`,
  allowing the user to input their ONCat login credentials securely.
- Upon successful login, the dialog closes, and the application can proceed with its functionality,
  utilizing the authenticated ONCat connection for data management tasks.

.. code:: python

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
            self.agent = pyoncat.ONCat(
                self.oncat_url,
                client_id=self.client_id,
                # Pass in token getter/setter callbacks here:
                token_getter=self.read_token,
                token_setter=self.write_token,
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

ONCatLogin Widget
-----------------
The following is a simple example of how to use the ONCatLogin widget in a PyQt application.
This example creates a main window with an ONCatLogin widget and two QListWidgets to display
the instrument lists for the SNS and HFIR facilities. The instrument lists are updated when
the connection status changes.

.. code:: python

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
