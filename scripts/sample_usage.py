import sys

from qtpy.QtWidgets import QApplication, QLabel, QListWidget, QVBoxLayout, QWidget

from pyoncatqt.login import ONCatLogin


class MainWindow(QWidget):
    """Main widget"""

    def __init__(self: QWidget, key: str = "shiver", parent: QWidget = None) -> None:
        super().__init__(parent=parent)

        layout = QVBoxLayout()

        # Create and add the Oncat widget
        self.oncat_widget = ONCatLogin(key=key, parent=self)
        self.oncat_widget.connection_updated.connect(self.update_instrument_lists)
        layout.addWidget(self.oncat_widget)

        # Add text input boxes for wavelength and run number
        self.sns_list = QListWidget()
        self.hfir_list = QListWidget()

        layout.addWidget(QLabel("SNS Instruments:"))
        layout.addWidget(self.sns_list)
        layout.addWidget(QLabel("HFIR Instruments:"))
        layout.addWidget(self.hfir_list)

        self.setLayout(layout)
        self.setWindowTitle("ONCat Application")
        self.oncat_widget.update_connection_status()

    def update_instrument_lists(self: QWidget, is_connected: bool) -> None:
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
