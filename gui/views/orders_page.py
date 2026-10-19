"""Orders page view."""

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Slot, QSettings

from gui.viewmodels.orders_vm import OrdersViewModel


class OrdersPage(QWidget):
    """Orders page — creates Excel from parsed data."""

    def __init__(self, viewmodel: OrdersViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._settings = QSettings("ProcurementAgent", "App")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Заказы")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Создание Excel-файлов из распарсенных данных")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Наименование", "Артикул", "Кол-во", "Ед.изм"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        self.btn_generate = QPushButton("Создать Excel")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        buttons_layout.addWidget(self.btn_generate)
        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #a6e3a1; font-size: 14px;")
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.btn_generate.clicked.connect(self._generate_excel)
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.vm.data_changed.connect(self.refresh_data)
        self.vm.orders_generated.connect(self._on_orders_generated)

    @Slot()
    def refresh_data(self):
        products = self.vm.products
        self.table.setRowCount(len(products))

        for i, p in enumerate(products):
            self.table.setItem(i, 0, QTableWidgetItem(p.name))
            self.table.setItem(i, 1, QTableWidgetItem(p.article))
            self.table.setItem(i, 2, QTableWidgetItem(str(p.quantity)))
            self.table.setItem(i, 3, QTableWidgetItem(p.unit))

    def _generate_excel(self):
        if not self.vm.products:
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите и распарсите файл на вкладке «Файлы».")
            return

        last_folder = self._settings.value("lastOutputFolder", "", type=str)

        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку для сохранения", last_folder
        )
        if not folder:
            return

        self._settings.setValue("lastOutputFolder", folder)
        self.vm.generate_orders(Path(folder))

    @Slot(list)
    def _on_orders_generated(self, files):
        self.status_label.setText(f"Создано файлов: {len(files)}")
        self.status_label.setStyleSheet("color: #a6e3a1; font-size: 14px;")
