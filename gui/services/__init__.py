"""Backend service abstraction and implementation."""

from gui.services.backend_impl import ProcurementBackend
from gui.services.backend_interface import BackendService

__all__ = ["BackendService", "ProcurementBackend"]
