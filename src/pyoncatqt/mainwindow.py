"""
Main Qt window
"""

from qtpy.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

from pyoncatqt.login import ONCatLogin


class MainWindow(QWidget):
    """Main widget"""

    def __init__(self, parent):
        super().__init__(parent=parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Create and add the Oncat widget
        self.oncat_widget = ONCatLogin(key="shiver", parent=self)
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
