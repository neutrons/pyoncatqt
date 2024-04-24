"""
Main Qt application
"""

import sys
from typing import Any, Dict

from qtpy.QtWidgets import QApplication, QMainWindow

from pyoncatqt.mainwindow import MainWindow  # noqa: E402
from pyoncatqt.version import __version__  # noqa: E402


class PyONCatQt(QMainWindow):
    """Main Package window"""

    __instance = None

    def __new__(cls: QMainWindow, **kwargs: Dict[str, Any]) -> QMainWindow:  # noqa ARG003
        if PyONCatQt.__instance is None:
            PyONCatQt.__instance = QMainWindow.__new__(cls)
        return PyONCatQt.__instance

    def __init__(self: QMainWindow, parent: QApplication = None, **kwargs: Dict[str, Any]) -> None:
        super().__init__(parent)
        key = kwargs.pop("key", "shiver")
        self.setWindowTitle(f"PYONCATQT - {__version__}")
        self.main_window = MainWindow(key, parent=self)
        self.setCentralWidget(self.main_window)


def gui() -> None:
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
