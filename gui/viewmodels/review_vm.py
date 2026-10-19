"""Review-queue ViewModel for gray-band article pairs."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService


class ReviewViewModel(QObject):
    data_changed = Signal()
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._pairs: list[dict] = []

    @property
    def pairs(self) -> list[dict]:
        return self._pairs.copy()

    def refresh(self):
        self._pairs = self._backend.get_review_pairs()
        self.data_changed.emit()

    def decide(self, article_a: str, article_b: str, decision: str):
        try:
            self._backend.decide_review_pair(article_a, article_b, decision)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))
