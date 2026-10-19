"""Run heavy callables off the GUI thread."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)


class _Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    _job = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._job.connect(self._execute)

    @Slot(object)
    def _execute(self, fn: Callable[[], Any]) -> None:
        try:
            self.finished.emit(fn())
        except Exception as exc:
            logger.exception("Background task failed")
            self.failed.emit(str(exc))


class TaskRunner(QObject):
    """Executes callables on a worker thread; delivers results on the GUI thread."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._deliver_result)
        self._worker.failed.connect(self._deliver_error)
        self._thread.start()
        self._busy = False
        self._on_result: Callable[[Any], None] | None = None
        self._on_error: Callable[[str], None] | None = None

    @property
    def busy(self) -> bool:
        return self._busy

    def shutdown(self) -> None:
        """Stop the worker thread. Must be called before the runner is destroyed."""
        self._thread.quit()
        self._thread.wait(2000)

    def __del__(self) -> None:
        self.shutdown()

    def run(
        self,
        fn: Callable[[], Any],
        on_result: Callable[[Any], None],
        on_error: Callable[[str], None],
    ) -> bool:
        """Start fn on the worker thread. Returns False while another task runs."""
        if self._busy:
            return False
        self._busy = True
        self._on_result = on_result
        self._on_error = on_error
        self._worker._job.emit(fn)
        return True

    @Slot(object)
    def _deliver_result(self, result: Any) -> None:
        self._busy = False
        callback, self._on_result, self._on_error = self._on_result, None, None
        if callback is not None:
            callback(result)

    @Slot(str)
    def _deliver_error(self, message: str) -> None:
        self._busy = False
        callback, self._on_result, self._on_error = self._on_error, None, None
        if callback is not None:
            callback(message)
