"""History page ViewModel."""

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService


class HistoryViewModel(QObject):
    """ViewModel for history page."""

    data_changed = Signal()

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._history: list[dict] = []

    @property
    def history(self) -> list[dict]:
        return self._history.copy()

    def refresh(self):
        self._history = self._backend.get_history()
        self.data_changed.emit()
