"""Reusable data table component."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


class DataTable(QTableWidget):
    """Reusable data table with word wrap and fixed column widths."""

    cell_double_clicked = Signal(int, int)
    cell_edited = Signal(int, int, str)

    # Ширина столбцов
    NAME_COL_WIDTH = 400
    QTY_COL_WIDTH = 200

    def __init__(self, headers: list[str], parent=None):
        super().__init__(parent)
        self.headers = headers
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self.setWordWrap(True)

        # Column resize
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.cellChanged.connect(self._on_cell_changed)

    def load_data(self, data: list[list[str]], editable_columns: list[int] | None = None):
        """Load data into the table."""
        self.setSortingEnabled(False)
        self.setRowCount(len(data))
        for row_idx, row_data in enumerate(data):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                item.setFlags(
                    item.flags() | Qt.ItemFlag.ItemIsEditable
                    if editable_columns and col_idx in editable_columns
                    else item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self.setItem(row_idx, col_idx, item)

        # Фиксируем ширину столбцов
        header = self.horizontalHeader()
        if "Наименование" in self.headers:
            name_col = self.headers.index("Наименование")
            header.setSectionResizeMode(name_col, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(name_col, self.NAME_COL_WIDTH)
        if "Количество" in self.headers:
            qty_col = self.headers.index("Количество")
            header.setSectionResizeMode(qty_col, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(qty_col, self.QTY_COL_WIDTH)

        self.setSortingEnabled(True)
        self.resizeRowsToContents()

    def load_data_with_status(self, data: list[list[str]], status_col: int = 0):
        """Load data with color-coded status column."""
        self.setSortingEnabled(False)
        self.setRowCount(len(data))
        status_colors = {
            "OK": "#a6e3a1",
            "Расхождение": "#fab387",
            "Отсутствует": "#f38ba8",
            "Лишний": "#89b4fa",
            "error": "#f38ba8",
            "success": "#a6e3a1",
            "no_email": "#fab387",
            "sent": "#a6e3a1",
        }

        for row_idx, row_data in enumerate(data):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                if col_idx == status_col and cell_data in status_colors:
                    item.setForeground(self._qcolor(status_colors[cell_data]))
                self.setItem(row_idx, col_idx, item)

        self.setSortingEnabled(True)
        self.resizeRowsToContents()

    def _on_cell_double_clicked(self, row: int, column: int):
        self.cell_double_clicked.emit(row, column)

    def _on_cell_changed(self, row: int, column: int):
        item = self.item(row, column)
        if item:
            self.cell_edited.emit(row, column, item.text())

    def get_row_data(self, row: int) -> list[str]:
        """Get all data from a row."""
        return [self.item(row, col).text() if self.item(row, col) else "" for col in range(self.columnCount())]

    def clear_data(self):
        """Clear all data."""
        self.setRowCount(0)
