"""Email page view."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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

        subtitle = QLabel("Управление email адресами и темой письма")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        # Subject field
        subject_layout = QHBoxLayout()
        subject_label = QLabel("Тема письма:")
        subject_label.setFixedWidth(120)
        subject_layout.addWidget(subject_label)
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Заявка от ДД.ММ.ГГГГ")
        subject_layout.addWidget(self.subject_input)
        layout.addLayout(subject_layout)

        # Email table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Поставщик", "Email", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить email")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_edit.setObjectName("secondaryButton")
        self.btn_send = QPushButton("Отправить все")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("secondaryButton")
        buttons_layout.addWidget(self.btn_add)
        buttons_layout.addWidget(self.btn_edit)
        buttons_layout.addWidget(self.btn_send)
        buttons_layout.addWidget(self.btn_refresh)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.btn_add.clicked.connect(self._add_email)
        self.btn_edit.clicked.connect(self._edit_email)
        self.btn_send.clicked.connect(self._send_emails)
        self.btn_refresh.clicked.connect(self.vm.refresh)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.subject_input.editingFinished.connect(self._on_subject_changed)
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

        # Update subject field (only if user is not editing)
        if not self.subject_input.hasFocus():
            self.subject_input.setText(self.vm.email_subject)

    def _on_cell_changed(self, row: int, column: int):
        if column == 1:
            supplier = self.table.item(row, 0).text()
            email = self.table.item(row, 1).text()
            self.vm.update_email(supplier, email)

    def _on_subject_changed(self):
        subject = self.subject_input.text().strip()
        if subject:
            self.vm.update_email_subject(subject)

    def _add_email(self):
        supplier, ok = QInputDialog.getText(self, "Новый поставщик", "Название поставщика:")
        if not ok or not supplier.strip():
            return
        supplier = supplier.strip()

        email, ok = QInputDialog.getText(self, "Email поставщика", f"Email для {supplier}:")
        if not ok or not email.strip():
            return

        self.vm.add_email(supplier, email.strip())
        self.status_label.setText(f"Добавлен email для {supplier}")

    def _edit_email(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Внимание", "Выберите строку в таблице")
            return

        supplier = self.table.item(row, 0).text()
        current_email = self.table.item(row, 1).text()

        email, ok = QInputDialog.getText(
            self,
            "Редактировать email",
            f"Email для {supplier}:",
            text=current_email,
        )
        if not ok:
            return

        self.vm.update_email(supplier, email.strip())
        self.status_label.setText(f"Email обновлён для {supplier}")

    def _send_emails(self):
        # Save subject before sending
        subject = self.subject_input.text().strip()
        if subject:
            self.vm.update_email_subject(subject)
        self.vm.send_emails()

    @Slot(list)
    def _on_emails_sent(self, results):
        for i, result in enumerate(results):
            if i < self.table.rowCount():
                status = result.get("status", "unknown")
                status_item = QTableWidgetItem(status)
                if status == "sent":
                    status_item.setForeground(Qt.GlobalColor.green)
                elif status in ("no_email", "no_order_file"):
                    status_item.setForeground(Qt.GlobalColor.yellow)
                elif status == "error":
                    status_item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(i, 2, status_item)

        sent_count = sum(1 for r in results if r.get("status") == "sent")
        self.status_label.setText(f"Отправлено: {sent_count} из {len(results)}")
