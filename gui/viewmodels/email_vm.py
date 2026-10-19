"""Email page ViewModel."""

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService
from gui.services.task_runner import TaskRunner
from models import SupplierGroup


class EmailViewModel(QObject):
    """ViewModel for email page."""

    data_changed = Signal()
    emails_sent = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._suppliers: list[SupplierGroup] = []
        self._emails: dict[str, str] = {}
        self._email_subject: str = ""
        self._runner = TaskRunner(self)

    @property
    def suppliers(self) -> list[SupplierGroup]:
        return self._suppliers.copy()

    @property
    def emails(self) -> dict[str, str]:
        return self._emails.copy()

    @property
    def email_subject(self) -> str:
        return self._email_subject

    def refresh(self):
        self._suppliers = self._backend.get_suppliers()
        self._emails = self._backend.get_emails()
        self._email_subject = self._backend.get_email_subject()
        self.data_changed.emit()

    def update_email(self, supplier: str, email: str):
        try:
            self._backend.update_email(supplier, email)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.refresh()

    def add_email(self, supplier: str, email: str):
        try:
            self._backend.update_email(supplier, email)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def update_email_subject(self, subject: str):
        self._email_subject = subject
        self._backend.save_email_subject(subject)

    def send_emails(self):
        if self._runner.busy:
            return
        self._runner.run(
            self._backend.send_emails,
            on_result=self._on_emails_sent,
            on_error=self.error_occurred.emit,
        )

    def _on_emails_sent(self, results: list):
        self.emails_sent.emit(results)
        self.refresh()
