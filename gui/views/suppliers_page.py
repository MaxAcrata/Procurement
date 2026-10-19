"""Suppliers page view."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QInputDialog
)
from PySide6.QtCore import Qt, Slot

from gui.components import DataTable
from gui.viewmodels.suppliers_vm import SuppliersViewModel


class SuppliersPage(QWidget):
    """Suppliers page with table view."""

    def __init__(self, viewmodel: SuppliersViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Поставщики")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Группировка товаров по поставщикам")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        self.table = DataTable(["Поставщик", "Наименование", "Артикул", "Количество"])
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_rename = QPushButton("Переименовать поставщика")
        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addWidget(self.btn_rename)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.btn_rename.clicked.connect(self._rename_supplier)
        self.vm.data_changed.connect(self.refresh_data)

    @Slot()
    def refresh_data(self):
        data = []
        for sg in self.vm.suppliers:
            for p in sg.products:
                data.append([sg.name, p.name, p.article, str(p.quantity)])
        self.table.load_data(data)

    def _rename_supplier(self):
        row = self.table.currentRow()
        if row < 0:
            return

        old_name = self.table.item(row, 0).text()
        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать поставщика",
            "Новое имя:",
            text=old_name
        )
        if ok and new_name and new_name != old_name:
            self.vm.rename_supplier(old_name, new_name)
