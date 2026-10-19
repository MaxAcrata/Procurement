"""Review queue page — gray-band article pairs awaiting decision."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView,
)
from PySide6.QtCore import Qt, Slot

from gui.viewmodels.review_vm import ReviewViewModel


class ReviewPage(QWidget):
    """Page for reviewing gray-band article pairs."""

    def __init__(self, viewmodel: ReviewViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Ревью пар")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Неоднозначные совпадения артикулов, требующие подтверждения")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Артикул A", "Артикул B", "Score", "Источник"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons_layout = QHBoxLayout()
        self.btn_confirm = QPushButton("Подтвердить")
        self.btn_reject = QPushButton("Отклонить")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        buttons_layout.addWidget(self.btn_confirm)
        buttons_layout.addWidget(self.btn_reject)
        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

    def _connect_signals(self):
        self.btn_confirm.clicked.connect(lambda: self._decide("confirmed"))
        self.btn_reject.clicked.connect(lambda: self._decide("rejected"))
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.vm.data_changed.connect(self.refresh_data)
        self.vm.error_occurred.connect(self.status_label.setText)

    @Slot()
    def refresh_data(self):
        pairs = self.vm.pairs
        self.table.setRowCount(len(pairs))
        for row, pair in enumerate(pairs):
            self.table.setItem(row, 0, QTableWidgetItem(pair["article_a"]))
            self.table.setItem(row, 1, QTableWidgetItem(pair["article_b"]))
            self.table.setItem(row, 2, QTableWidgetItem(f"{pair['score']:.3f}"))
            self.table.setItem(row, 3, QTableWidgetItem(pair["source"]))

    def _decide(self, decision: str):
        row = self.table.currentRow()
        if row < 0:
            self.status_label.setText("Выберите пару в таблице")
            return
        article_a = self.table.item(row, 0).text()
        article_b = self.table.item(row, 1).text()
        self.vm.decide(article_a, article_b, decision)
