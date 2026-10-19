"""Procurement Agent — GUI entry point."""

from __future__ import annotations

import sys

from logging_setup import setup_logging


def main() -> None:
    setup_logging()

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from gui.main_window import MainWindow
    from gui.styles.dark_theme import DARK_THEME

    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
