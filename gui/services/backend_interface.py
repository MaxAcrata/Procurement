"""Backend service interface — abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from models import ComparisonItem, Product, SupplierGroup

__all__ = ["BackendService"]


class BackendService(ABC):
    """Interface for backend operations."""

    @abstractmethod
    def process_files(self, files: list[Path]) -> dict:
        """Process uploaded files and return status."""
        ...

    @abstractmethod
    def get_parsed_data(self) -> list[Product]:
        """Return parsed product data."""
        ...

    @abstractmethod
    def update_product(self, index: int, product: Product) -> None:
        """Update a product in the parsed data."""
        ...

    @abstractmethod
    def delete_product(self, index: int) -> None:
        """Delete a product from the parsed data."""
        ...

    @abstractmethod
    def get_suppliers(self) -> list[SupplierGroup]:
        """Return grouped supplier data."""
        ...

    @abstractmethod
    def rename_supplier(self, old_name: str, new_name: str) -> None:
        """Rename a supplier."""
        ...

    @abstractmethod
    def generate_orders(self, output_dir: Path) -> list[Path]:
        """Generate purchase order files."""
        ...

    @abstractmethod
    def compare(self, order_path: Path, invoice_paths: list[Path]) -> list[ComparisonItem]:
        """Compare order against invoices."""
        ...

    @abstractmethod
    def get_emails(self) -> dict[str, str]:
        """Return supplier emails."""
        ...

    @abstractmethod
    def update_email(self, supplier: str, email: str) -> None:
        """Update supplier email."""
        ...

    @abstractmethod
    def get_email_subject(self) -> str:
        """Return saved email subject."""
        ...

    @abstractmethod
    def save_email_subject(self, subject: str) -> None:
        """Persist email subject for future use."""
        ...

    @abstractmethod
    def send_emails(self, emails_db_path: Path | None = None) -> list[dict]:
        """Send emails to suppliers."""
        ...

    @abstractmethod
    def get_history(self) -> list[dict]:
        """Return operation history."""
        ...
