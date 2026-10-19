"""Suppliers page ViewModel."""

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService
from models import SupplierGroup


class SuppliersViewModel(QObject):
    """ViewModel for suppliers page."""

    data_changed = Signal()
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._suppliers: list[SupplierGroup] = []

    @property
    def suppliers(self) -> list[SupplierGroup]:
        return self._suppliers.copy()

    def refresh(self):
        self._suppliers = self._backend.get_suppliers()
        self.data_changed.emit()

    def rename_supplier(self, old_name: str, new_name: str):
        try:
            self._backend.rename_supplier(old_name, new_name)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))
