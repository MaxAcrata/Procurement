"""Parsed data page view."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QHeaderView
)
from PySide6.QtCore import Qt, Slot

from gui.components import DataTable
from gui.viewmodels.parsed_data_vm import ParsedDataViewModel


class ParsedDataPage(QWidget):
    """Parsed data page with table view."""

    def __init__(self, viewmodel: ParsedDataViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Обработанные данные")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.filter_supplier = QComboBox()
        self.filter_supplier.addItem("Все поставщики")
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.filter_supplier)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.table = DataTable(["Поставщик", "Наименование", "Артикул", "Количество"])
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.setObjectName("dangerButton")
        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addWidget(self.btn_delete)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.search_input.textChanged.connect(self._filter_data)
        self.filter_supplier.currentTextChanged.connect(self._filter_data)
        self.vm.data_changed.connect(self.refresh_data)

    @Slot()
    def refresh_data(self):
        products = self.vm.products
        self.table.load_data([
            [p.supplier, p.name, p.article, str(p.quantity)]
            for p in products
        ])
        self._update_supplier_filter()

    def _update_supplier_filter(self):
        current = self.filter_supplier.currentText()
        self.filter_supplier.clear()
        self.filter_supplier.addItem("Все поставщики")
        for s in self.vm.get_suppliers():
            self.filter_supplier.addItem(s)
        idx = self.filter_supplier.findText(current)
        if idx >= 0:
            self.filter_supplier.setCurrentIndex(idx)

    def _filter_data(self):
        search = self.search_input.text().lower()
        supplier = self.filter_supplier.currentText()

        products = self.vm.products
        filtered = [
            p for p in products
            if (not search or search in p.name.lower() or search in p.article.lower())
            and (supplier == "Все поставщики" or p.supplier == supplier)
        ]

        self.table.load_data([
            [p.supplier, p.name, p.article, str(p.quantity)]
            for p in filtered
        ])

    def _delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.vm.delete_product(row)
