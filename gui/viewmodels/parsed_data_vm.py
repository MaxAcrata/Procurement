"""Parsed data page ViewModel."""

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService
from models import Product


class ParsedDataViewModel(QObject):
    """ViewModel for parsed data page."""

    data_changed = Signal()
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._products: list[Product] = []

    @property
    def products(self) -> list[Product]:
        return self._products.copy()

    def refresh(self):
        self._products = self._backend.get_parsed_data()
        self.data_changed.emit()

    def update_product(self, index: int, product: Product):
        try:
            self._backend.update_product(index, product)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def delete_product(self, index: int):
        try:
            self._backend.delete_product(index)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def get_suppliers(self) -> list[str]:
        return list(set(p.supplier for p in self._products))
