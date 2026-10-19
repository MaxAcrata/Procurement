"""History page view."""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.viewmodels.history_vm import HistoryViewModel


class HistoryPage(QWidget):
    """History page with operation log."""

    def __init__(self, viewmodel: HistoryViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("История операций")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Время", "Действие", "Детали"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        layout.addWidget(self.btn_refresh)

    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.vm.data_changed.connect(self.refresh_data)

    @Slot()
    def refresh_data(self):
        history = self.vm.history
        self.table.setRowCount(len(history))

        for i, entry in enumerate(reversed(history)):
            timestamp = entry.get("timestamp", "")
            action = entry.get("action", "")
            details = entry.get("details", "")

            action_labels = {
                "process": "Обработка файлов",
                "generate": "Генерация заказов",
                "compare": "Сравнение",
                "email": "Отправка email",
            }

            self.table.setItem(i, 0, QTableWidgetItem(timestamp))
            self.table.setItem(i, 1, QTableWidgetItem(action_labels.get(action, action)))
            self.table.setItem(i, 2, QTableWidgetItem(details))
