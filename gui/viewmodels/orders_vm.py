"""Orders page ViewModel."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService
from gui.services.task_runner import TaskRunner
from models import Product


class OrdersViewModel(QObject):
    """ViewModel for orders page — works with parsed products directly."""

    data_changed = Signal()
    orders_generated = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._products: list[Product] = []
        self._generated_files: list[Path] = []
        self._runner = TaskRunner(self)

    @property
    def products(self) -> list[Product]:
        return self._products.copy()

    @property
    def generated_files(self) -> list[Path]:
        return self._generated_files.copy()

    def refresh(self):
        self._products = self._backend.get_parsed_data()
        self.data_changed.emit()

    def generate_orders(self, output_dir: Path = Path("output")):
        if self._runner.busy:
            return
        self._runner.run(
            lambda: self._backend.generate_orders(output_dir),
            on_result=self._on_orders_generated,
            on_error=self.error_occurred.emit,
        )

    def _on_orders_generated(self, files: list):
        self._generated_files = files
        self.orders_generated.emit(self._generated_files)
        self.refresh()
