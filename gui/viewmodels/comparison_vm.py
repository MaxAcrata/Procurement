"""Comparison page ViewModel."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService
from gui.services.task_runner import TaskRunner
from models import ComparisonItem, SupplierMatchStatus


class ComparisonViewModel(QObject):
    """ViewModel for comparison page."""

    comparison_done = Signal(list, dict)
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._results: list[ComparisonItem] = []
        self._summary: dict = {}
        self._runner = TaskRunner(self)

    @property
    def results(self) -> list[ComparisonItem]:
        return self._results.copy()

    @property
    def summary(self) -> dict:
        return self._summary.copy()

    def compare(self, order_path: Path, invoice_paths: list[Path]):
        if self._runner.busy:
            return
        paths = list(invoice_paths)

        def work():
            results = self._backend.compare(order_path, paths)
            self._results = results
            self._summary = self._calculate_summary()
            return (results, self._summary)

        def done(payload):
            results, summary = payload
            self.comparison_done.emit(results, summary)

        self._runner.run(work, on_result=done, on_error=self.error_occurred.emit)

    def _calculate_summary(self) -> dict:
        total = len(self._results)
        if total == 0:
            return {"total": 0, "match_pct": 0, "ok": 0, "mismatches": 0, "missing": 0, "extra": 0}

        ok = sum(1 for r in self._results if r.status == SupplierMatchStatus.OK)
        return {
            "total": total,
            "match_pct": round(ok / total * 100, 1),
            "ok": ok,
            "mismatches": sum(1 for r in self._results if r.status == SupplierMatchStatus.MISMATCH_QUANTITY),
            "missing": sum(1 for r in self._results if r.status == SupplierMatchStatus.MISSING),
            "extra": sum(1 for r in self._results if r.status == SupplierMatchStatus.EXTRA),
        }
