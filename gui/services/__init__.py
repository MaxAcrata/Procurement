"""Backend service abstraction and implementation."""

from gui.services.backend_interface import BackendService
from gui.services.backend_impl import ProcurementBackend

__all__ = ["BackendService", "ProcurementBackend"]
