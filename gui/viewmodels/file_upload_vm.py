"""File upload page ViewModel."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService


class FileUploadViewModel(QObject):
    """ViewModel for file upload page."""

    files_changed = Signal(list)
    processing_started = Signal()
    processing_finished = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._files: list[Path] = []

    @property
    def files(self) -> list[Path]:
        return self._files.copy()

    def add_files(self, paths: list[str]):
        for p in paths:
            path = Path(p)
            if path.exists() and path not in self._files:
                self._files.append(path)
        self.files_changed.emit(self._files)

    def remove_file(self, index: int):
        if 0 <= index < len(self._files):
            self._files.pop(index)
            self.files_changed.emit(self._files)

    def clear_files(self):
        self._files.clear()
        self.files_changed.emit(self._files)

    def process_files(self):
        if not self._files:
            self.error_occurred.emit("No files to process")
            return

        self.processing_started.emit()
        try:
            result = self._backend.process_files(self._files)
            self.processing_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
