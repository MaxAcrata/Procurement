"""Comparison page view."""

from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.viewmodels.comparison_vm import ComparisonViewModel


class ComparisonPage(QWidget):
    """Comparison page with split layout."""

    def __init__(self, viewmodel: ComparisonViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._order_path = None
        self._invoice_paths = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Сравнение документов")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        files_layout = QHBoxLayout()

        order_frame = QFrame()
        order_frame.setFrameShape(QFrame.Shape.StyledPanel)
        order_layout = QVBoxLayout(order_frame)
        order_layout.addWidget(QLabel("Заявка:"))
        self.order_label = QLabel("Не выбран")
        self.order_label.setWordWrap(True)
        order_layout.addWidget(self.order_label)
        self.btn_select_order = QPushButton("Выбрать заявку")
        order_layout.addWidget(self.btn_select_order)
        files_layout.addWidget(order_frame)

        invoice_frame = QFrame()
        invoice_frame.setFrameShape(QFrame.Shape.StyledPanel)
        invoice_layout = QVBoxLayout(invoice_frame)
        invoice_layout.addWidget(QLabel("Счета:"))
        self.invoice_label = QLabel("Не выбраны")
        self.invoice_label.setWordWrap(True)
        invoice_layout.addWidget(self.invoice_label)
        self.btn_select_invoice = QPushButton("Выбрать счета")
        invoice_layout.addWidget(self.btn_select_invoice)
        files_layout.addWidget(invoice_frame)

        layout.addLayout(files_layout)

        self.btn_compare = QPushButton("Сравнить")
        layout.addWidget(self.btn_compare)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.summary_layout = QHBoxLayout()
        self.summary_labels = {}
        for key, text in [
            ("total", "Всего"),
            ("ok", "Совпадений"),
            ("mismatches", "Расхождения"),
            ("missing", "Отсутствует"),
            ("extra", "Лишний"),
        ]:
            frame = QFrame()
            frame.setStyleSheet("QFrame { background-color: #313244; border-radius: 8px; padding: 12px; }")
            v_layout = QVBoxLayout(frame)
            v_layout.addWidget(QLabel(text))
            value_label = QLabel("0")
            value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa;")
            v_layout.addWidget(value_label)
            self.summary_labels[key] = value_label
            self.summary_layout.addWidget(frame)
        layout.addLayout(self.summary_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [
                "Артикул в Заявке",
                "Артикул в Счете",
                "Кол-во в Заявке",
                "Кол-во в Счете",
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def _connect_signals(self):
        self.btn_select_order.clicked.connect(self._select_order)
        self.btn_select_invoice.clicked.connect(self._select_invoices)
        self.btn_compare.clicked.connect(self._compare)
        self.vm.comparison_done.connect(self._on_comparison_done)

    def _select_order(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл заявки", "", "Excel (*.xlsx);;Все файлы (*)")
        if path:
            self._order_path = path
            self.order_label.setText(path.split("/")[-1].split("\\")[-1])

    def _select_invoices(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы счетов", "", "Excel (*.xlsx);;Все файлы (*)")
        if paths:
            self._invoice_paths = paths
            self.invoice_label.setText("\n".join(p.split("/")[-1].split("\\")[-1] for p in paths))

    def _compare(self):
        if self._order_path and self._invoice_paths:
            self.status_label.setText("")
            from pathlib import Path

            self.vm.compare(Path(self._order_path), [Path(p) for p in self._invoice_paths])
        else:
            self.status_label.setText("Выберите заявку и счета для сравнения")

    @Slot(list, dict)
    def _on_comparison_done(self, results, summary):
        for key, label in self.summary_labels.items():
            label.setText(str(summary.get(key, 0)))

        green = QColor("#a6e3a1")
        red = QColor("#f38ba8")

        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            # Артикул в Заявке
            self.table.setItem(i, 0, QTableWidgetItem(r.product.article))

            # Артикул в Счете
            inv_article = r.invoice_article if r.invoice_article else "-"
            self.table.setItem(i, 1, QTableWidgetItem(inv_article))

            # Кол-во в Заявке
            qty_order = str(int(r.product.quantity)) if r.product.quantity else "-"
            qty_item = QTableWidgetItem(qty_order)
            self.table.setItem(i, 2, qty_item)

            # Кол-во в Счете
            if r.invoice_quantity is not None:
                qty_invoice = str(int(r.invoice_quantity))
                qty_inv_item = QTableWidgetItem(qty_invoice)
            else:
                qty_inv_item = QTableWidgetItem("-")

            # Цвет: зелёный если совпадают, красный если нет
            if r.invoice_quantity is not None and r.product.quantity == r.invoice_quantity:
                qty_item.setForeground(green)
                qty_inv_item.setForeground(green)
            else:
                qty_item.setForeground(red)
                qty_inv_item.setForeground(red)

            self.table.setItem(i, 3, qty_inv_item)
