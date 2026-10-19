"""Main application window."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.components import StatusBadge
from gui.services.backend_impl import ProcurementBackend
from gui.viewmodels.comparison_vm import ComparisonViewModel
from gui.viewmodels.email_vm import EmailViewModel
from gui.viewmodels.file_upload_vm import FileUploadViewModel
from gui.viewmodels.history_vm import HistoryViewModel
from gui.viewmodels.orders_vm import OrdersViewModel
from gui.viewmodels.parsed_data_vm import ParsedDataViewModel
from gui.viewmodels.review_vm import ReviewViewModel
from gui.viewmodels.suppliers_vm import SuppliersViewModel
from gui.views import (
    ComparisonPage,
    EmailPage,
    FileUploadPage,
    HistoryPage,
    OrdersPage,
    ParsedDataPage,
    ReviewPage,
    SuppliersPage,
)


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation."""

    NAV_ITEMS = [
        ("files", "Файлы", FileUploadPage),
        ("data", "Данные", ParsedDataPage),
        ("suppliers", "Поставщики", SuppliersPage),
        ("orders", "Заказы", OrdersPage),
        ("compare", "Сравнение", ComparisonPage),
        ("review", "Ревью пар", ReviewPage),
        ("email", "Email", EmailPage),
        ("history", "История", HistoryPage),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Procurement Agent")
        self.setMinimumSize(1200, 700)

        self.backend = ProcurementBackend()
        self._setup_viewmodels()
        self._setup_ui()
        self._connect_signals()

        self._navigate_to("files")

    def _setup_viewmodels(self):
        self.vm_file_upload = FileUploadViewModel(self.backend)
        self.vm_parsed_data = ParsedDataViewModel(self.backend)
        self.vm_suppliers = SuppliersViewModel(self.backend)
        self.vm_orders = OrdersViewModel(self.backend)
        self.vm_comparison = ComparisonViewModel(self.backend)
        self.vm_review = ReviewViewModel(self.backend)
        self.vm_email = EmailViewModel(self.backend)
        self.vm_history = HistoryViewModel(self.backend)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        top_bar = self._create_top_bar()
        content_layout.addWidget(top_bar)

        self.stack = QStackedWidget()
        self.pages = {}
        self._create_pages()
        content_layout.addWidget(self.stack)

        main_layout.addLayout(content_layout)

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(4)

        logo = QLabel("PA")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 24px; font-weight: bold; color: #89b4fa; padding: 16px;")
        layout.addWidget(logo)

        self.nav_buttons = {}
        for key, text, _ in self.NAV_ITEMS:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._navigate_to(k))
            self.nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()
        return sidebar

    def _create_top_bar(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(50)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(16, 8, 16, 8)

        self.page_title = QLabel("Файлы")
        self.page_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.page_title)

        layout.addStretch()

        self.status_badge = StatusBadge("idle")
        layout.addWidget(self.status_badge)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        return top_bar

    def _create_pages(self):
        page_map = {
            "files": FileUploadPage(self.vm_file_upload),
            "data": ParsedDataPage(self.vm_parsed_data),
            "suppliers": SuppliersPage(self.vm_suppliers),
            "orders": OrdersPage(self.vm_orders),
            "compare": ComparisonPage(self.vm_comparison),
            "review": ReviewPage(self.vm_review),
            "email": EmailPage(self.vm_email),
            "history": HistoryPage(self.vm_history),
        }

        for key, _text, _ in self.NAV_ITEMS:
            page = page_map[key]
            self.pages[key] = page
            self.stack.addWidget(page)

    def _connect_signals(self):
        self.vm_file_upload.processing_started.connect(self._on_processing_started)
        self.vm_file_upload.processing_finished.connect(self._on_processing_finished)
        self.vm_file_upload.error_occurred.connect(self._on_error)

    def _navigate_to(self, key: str):
        if key in self.pages:
            self.stack.setCurrentWidget(self.pages[key])
            self.page_title.setText(dict((k, t) for k, t, _ in self.NAV_ITEMS).get(key, ""))

            for k, btn in self.nav_buttons.items():
                btn.setChecked(k == key)

            if key == "data":
                self.vm_parsed_data.refresh()
            elif key == "suppliers":
                self.vm_suppliers.refresh()
            elif key == "orders":
                self.vm_orders.refresh()
            elif key == "review":
                self.vm_review.refresh()
            elif key == "email":
                self.vm_email.refresh()
            elif key == "history":
                self.vm_history.refresh()

    @Slot()
    def _on_processing_started(self):
        self.status_badge.set_status("processing")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

    @Slot(dict)
    def _on_processing_finished(self, result):
        self.status_badge.set_status("success" if result.get("status") == "success" else "error")
        self.progress_bar.setVisible(False)
        # Refresh data on other pages
        if result.get("status") == "success":
            self.vm_orders.refresh()

    @Slot(str)
    def _on_error(self, message: str):
        self.status_badge.set_status("error")
        self.progress_bar.setVisible(False)
