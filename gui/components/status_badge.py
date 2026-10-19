"""Status badge component."""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt


class StatusBadge(QLabel):
    """Status badge label with color coding."""

    STYLES = {
        "idle": ("Idle", "#6c7086", "#313244"),
        "processing": ("Processing...", "#89b4fa", "#313244"),
        "success": ("Success", "#a6e3a1", "#313244"),
        "error": ("Error", "#f38ba8", "#313244"),
        "warning": ("Warning", "#fab387", "#313244"),
    }

    def __init__(self, status: str = "idle", parent=None):
        super().__init__(parent)
        self.set_status(status)

    def set_status(self, status: str):
        """Set the badge status."""
        if status in self.STYLES:
            text, color, bg = self.STYLES[status]
            self.setText(text)
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    color: {color};
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)
        else:
            self.setText(status)
            self.setStyleSheet("""
                QLabel {
                    background-color: #313244;
                    color: #cdd6f4;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
