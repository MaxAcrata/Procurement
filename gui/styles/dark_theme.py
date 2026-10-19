"""Dark theme QSS styles."""

DARK_THEME = """
/* Main Window */
QMainWindow {
    background-color: #1e1e2e;
}

/* Sidebar */
#sidebar {
    background-color: #181825;
    border-right: 1px solid #313244;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #cdd6f4;
    border: none;
    border-radius: 8px;
    padding: 12px 16px;
    text-align: left;
    font-size: 14px;
    margin: 2px 8px;
}

#sidebar QPushButton:hover {
    background-color: #313244;
}

#sidebar QPushButton:checked {
    background-color: #45475a;
    color: #89b4fa;
}

/* Top Bar */
#topBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    padding: 8px 16px;
}

/* Tables */
QTableWidget {
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    color: #cdd6f4;
    gridline-color: #313244;
    border: none;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: #45475a;
    outline: none;
}

QTableWidget::item {
    padding: 8px;
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QTableWidget::item:alternate {
    background-color: #181825;
    color: #cdd6f4;
}

QTableWidget::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}

QTableWidget::item:hover {
    background-color: #313244;
    color: #cdd6f4;
}

QHeaderView::section {
    background-color: #181825;
    color: #89b4fa;
    border: none;
    border-bottom: 2px solid #313244;
    padding: 8px;
    font-weight: bold;
}

/* Buttons */
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: bold;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #74c7ec;
}

QPushButton:pressed {
    background-color: #89dceb;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

#dangerButton {
    background-color: #f38ba8;
}

#dangerButton:hover {
    background-color: #eba0ac;
}

#secondaryButton {
    background-color: #45475a;
    color: #cdd6f4;
}

#secondaryButton:hover {
    background-color: #585b70;
}

/* Line Edit */
QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 2px solid #45475a;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}

QLineEdit:focus {
    border-color: #89b4fa;
}

/* Combo Box */
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 2px solid #45475a;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}

QComboBox:hover {
    border-color: #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
    border: 1px solid #45475a;
}

/* Progress Bar */
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}

/* Scroll Bar */
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

/* Tree Widget */
QTreeWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: none;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}

QTreeWidget::item {
    padding: 8px;
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QTreeWidget::item:alternate {
    background-color: #181825;
    color: #cdd6f4;
}

QTreeWidget::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}

QTreeWidget::item:hover {
    background-color: #313244;
    color: #cdd6f4;
}

QTreeWidget::branch {
    background-color: #1e1e2e;
}

/* Labels */
QLabel {
    color: #cdd6f4;
}

#titleLabel {
    font-size: 24px;
    font-weight: bold;
    color: #cdd6f4;
}

#subtitleLabel {
    font-size: 14px;
    color: #6c7086;
}

/* Status Badge */
#statusBadge {
    background-color: #45475a;
    color: #a6e3a1;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: bold;
}

#errorBadge {
    background-color: #45475a;
    color: #f38ba8;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: bold;
}

#warningBadge {
    background-color: #45475a;
    color: #fab387;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: bold;
}

/* Group Box */
QGroupBox {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 16px;
    font-weight: bold;
    color: #cdd6f4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: #89b4fa;
}

/* Tab Widget */
QTabWidget::pane {
    border: none;
    background-color: #1e1e2e;
}

QTabBar::tab {
    background-color: #313244;
    color: #cdd6f4;
    border: none;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QTabBar::tab:selected {
    background-color: #45475a;
    color: #89b4fa;
}

QTabBar::tab:hover {
    background-color: #585b70;
}

/* File Drop Zone */
#dropZone {
    background-color: #313244;
    border: 2px dashed #585b70;
    border-radius: 12px;
    padding: 40px;
    min-height: 150px;
}

#dropZone:hover {
    border-color: #89b4fa;
    background-color: #45475a;
}

/* Splitter */
QSplitter::handle {
    background-color: #313244;
}

QSplitter::handle:horizontal {
    width: 4px;
}

QSplitter::handle:vertical {
    height: 4px;
}

/* Message Box */
QMessageBox {
    background-color: #1e1e2e;
}

QMessageBox QLabel {
    color: #cdd6f4;
}

/* Dialog */
QDialog {
    background-color: #1e1e2e;
}
"""
