"""
Main Qt application
"""

import sys

from qtpy.QtWidgets import QApplication, QMainWindow

from pyoncatqt.mainwindow import MainWindow  # noqa: E402 pylint: disable=wrong-import-position
from pyoncatqt.version import __version__  # noqa: E402 pylint: disable=wrong-import-position


class PyONCatQt(QMainWindow):
    """Main Package window"""

    __instance = None

    def __new__(cls):
        if PyONCatQt.__instance is None:
            PyONCatQt.__instance = QMainWindow.__new__(cls)  # pylint: disable=no-value-for-parameter
        return PyONCatQt.__instance

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"PYONCATQT - {__version__}")
        self.main_window = MainWindow(self)
        self.setCentralWidget(self.main_window)


def gui():
    """
    Main entry point for Qt application
    """
    input_flags = sys.argv[1::]
    if "--v" in input_flags or "--version" in input_flags:
        print(__version__)
        sys.exit()
    else:
        app = QApplication(sys.argv)
        window = PyONCatQt()
        window.show()
        sys.exit(app.exec_())
