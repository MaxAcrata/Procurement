"""Email page view."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt, Slot

from gui.viewmodels.email_vm import EmailViewModel


class EmailPage(QWidget):
    """Email page with editing and sending."""

    def __init__(self, viewmodel: EmailViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Отправка email")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Управление email адресами поставщиков")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Поставщик", "Email", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        buttons_layout = QHBoxLayout()
        self.btn_send = QPushButton("Отправить все")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        buttons_layout.addWidget(self.btn_send)
        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.btn_send.clicked.connect(self.vm.send_emails)
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.vm.data_changed.connect(self.refresh_data)
        self.vm.emails_sent.connect(self._on_emails_sent)
        self.vm.error_occurred.connect(self._on_error)

    @Slot(str)
    def _on_error(self, message: str):
        self.status_label.setText(message)

    @Slot()
    def refresh_data(self):
        suppliers = self.vm.suppliers
        emails = self.vm.emails

        self.table.blockSignals(True)
        self.table.setRowCount(len(suppliers))

        for i, sg in enumerate(suppliers):
            self.table.setItem(i, 0, QTableWidgetItem(sg.name))
            email_item = QTableWidgetItem(emails.get(sg.name, ""))
            self.table.setItem(i, 1, email_item)
            self.table.setItem(i, 2, QTableWidgetItem("Ожидание"))

        self.table.blockSignals(False)

    def _on_cell_changed(self, row: int, column: int):
        if column == 1:
            supplier = self.table.item(row, 0).text()
            email = self.table.item(row, 1).text()
            self.vm.update_email(supplier, email)

    @Slot(list)
    def _on_emails_sent(self, results):
        for i, result in enumerate(results):
            if i < self.table.rowCount():
                status = result.get("status", "unknown")
                status_item = QTableWidgetItem(status)
                if status == "sent":
                    status_item.setForeground(Qt.GlobalColor.green)
                elif status == "no_email":
                    status_item.setForeground(Qt.GlobalColor.yellow)
                self.table.setItem(i, 2, status_item)

        sent_count = sum(1 for r in results if r.get("status") == "sent")
        self.status_label.setText(f"Отправлено: {sent_count} из {len(results)}")
