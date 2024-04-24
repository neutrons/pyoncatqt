from unittest.mock import MagicMock

import pytest
from pyoncatqt.mainwindow import MainWindow
from qtpy.QtWidgets import QLabel, QListWidget


def test_update_instrument_lists(qtbot: pytest.fixture) -> None:
    main_window = MainWindow(None)
    qtbot.addWidget(main_window)

    oncat_widget_mock = MagicMock()
    oncat_widget_mock.agent.Instrument.list.return_value = [{"name": "Instrument1"}, {"name": "Instrument2"}]

    main_window.oncat_widget = oncat_widget_mock

    main_window.sns_list = QListWidget()
    main_window.layout().addWidget(main_window.sns_list)
    main_window.layout().addWidget(QLabel("SNS Instruments:"))

    main_window.hfir_list = QListWidget()
    main_window.layout().addWidget(main_window.hfir_list)
    main_window.layout().addWidget(QLabel("HFIR Instruments:"))

    main_window.update_instrument_lists(True)

    # Check if the instruments were added to the QListWidgets
    assert main_window.sns_list.count() == 2
    assert main_window.hfir_list.count() == 2

    # Check if the correct instruments were added
    assert main_window.sns_list.item(0).text() == "Instrument1"
    assert main_window.sns_list.item(1).text() == "Instrument2"
    assert main_window.hfir_list.item(0).text() == "Instrument1"
    assert main_window.hfir_list.item(1).text() == "Instrument2"
