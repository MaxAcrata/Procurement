"""File upload page view."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.components import FileDropZone
from gui.viewmodels.file_upload_vm import FileUploadViewModel


class FileUploadPage(QWidget):
    """File upload page with drag & drop."""

    def __init__(self, viewmodel: FileUploadViewModel, parent=None):
        super().__init__(parent)
        self.vm = viewmodel
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Загрузка документов")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Загрузите файлы для обработки")
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        self.drop_zone = FileDropZone()
        layout.addWidget(self.drop_zone)

        buttons_layout = QHBoxLayout()
        self.btn_add = QPushButton("Выбрать файлы")
        self.btn_add.setObjectName("secondaryButton")
        self.btn_process = QPushButton("Обработать")
        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.setObjectName("dangerButton")
        buttons_layout.addWidget(self.btn_add)
        buttons_layout.addWidget(self.btn_process)
        buttons_layout.addWidget(self.btn_clear)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["Имя", "Тип", "Статус"])
        self.file_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.verticalHeader().setVisible(False)
        layout.addWidget(self.file_table)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.drop_zone.files_dropped.connect(self.vm.add_files)
        self.btn_add.clicked.connect(self._open_file_dialog)
        self.btn_process.clicked.connect(self._process_files)
        self.btn_clear.clicked.connect(self.vm.clear_files)
        self.btn_clear.clicked.connect(self._clear_table)
        self.vm.files_changed.connect(self._update_table)
        self.vm.processing_finished.connect(self._on_processing_finished)
        self.vm.error_occurred.connect(self._on_error)

    def _open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы",
            "",
            "Все файлы (*.pdf *.docx *.xlsx *.png *.jpg *.jpeg);;PDF (*.pdf);;Word (*.docx);;Excel (*.xlsx);;Изображения (*.png *.jpg *.jpeg)",
        )
        if files:
            self.vm.add_files(files)

    def _process_files(self):
        if not self.vm.files:
            QMessageBox.warning(self, "Внимание", "Сначала добавьте файлы для обработки")
            return
        self.status_label.setText("Обработка...")
        self.status_label.setStyleSheet(
            "color: #fab387; font-size: 14px; font-weight: bold; background-color: #313244; border-radius: 6px; padding: 8px 12px;"
        )
        self.btn_process.setEnabled(False)
        self.vm.process_files()

    @Slot(list)
    def _update_table(self, files):
        self.file_table.setRowCount(len(files))
        for i, f in enumerate(files):
            name_item = QTableWidgetItem(f.name)
            type_item = QTableWidgetItem(f.suffix.upper())
            status_item = QTableWidgetItem("Готов")
            status_item.setForeground(Qt.GlobalColor.green)
            self.file_table.setItem(i, 0, name_item)
            self.file_table.setItem(i, 1, type_item)
            self.file_table.setItem(i, 2, status_item)

    @Slot(dict)
    def _on_processing_finished(self, result):
        self.btn_process.setEnabled(True)
        count = result.get("count", 0)
        if result.get("status") == "success":
            self.status_label.setText(f"Обработано: {count} позиций")
            self.status_label.setStyleSheet(
                "color: #a6e3a1; font-size: 14px; font-weight: bold; background-color: #313244; border-radius: 6px; padding: 8px 12px;"
            )
            for i in range(self.file_table.rowCount()):
                status_item = QTableWidgetItem("Обработано")
                status_item.setForeground(Qt.GlobalColor.green)
                self.file_table.setItem(i, 2, status_item)
        else:
            self.status_label.setText("Ошибка обработки")
            self.status_label.setStyleSheet(
                "color: #f38ba8; font-size: 14px; font-weight: bold; background-color: #313244; border-radius: 6px; padding: 8px 12px;"
            )
            errors = result.get("errors", [])
            if errors:
                QMessageBox.warning(self, "Ошибки", "\n".join(errors[:5]))

    @Slot(str)
    def _on_error(self, message: str):
        self.btn_process.setEnabled(True)
        self.status_label.setText(f"Ошибка: {message}")
        self.status_label.setStyleSheet(
            "color: #f38ba8; font-size: 14px; font-weight: bold; background-color: #313244; border-radius: 6px; padding: 8px 12px;"
        )

    def _clear_table(self):
        self.file_table.setRowCount(0)
        self.status_label.setText("")
