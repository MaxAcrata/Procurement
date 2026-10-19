"""Data models for the procurement agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

__all__ = [
    "SupplierMatchStatus",
    "Product",
    "ComparisonItem",
    "SupplierGroup",
    "DocumentParseResult",
    "PipelineResult",
    "ReviewPair",
]


class SupplierMatchStatus(Enum):
    OK = "ok"
    MISMATCH_QUANTITY = "mismatch_quantity"
    MISSING = "missing"
    EXTRA = "extra"


@dataclass
class Product:
    name: str
    article: str
    quantity: float
    supplier: str = "UNKNOWN"
    unit: str = ""
    ocr_confidence: float | None = None


@dataclass
class ComparisonItem:
    product: Product
    invoice_article: str = ""
    invoice_quantity: float | None = None
    status: SupplierMatchStatus = SupplierMatchStatus.OK
    diff: float = 0.0


@dataclass
class SupplierGroup:
    name: str
    products: list[Product] = field(default_factory=list)


@dataclass
class DocumentParseResult:
    file_path: Path
    file_type: str
    products: list[Product]
    raw_text: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    status: str = "success"
    summary: str = ""
    suppliers: list[SupplierGroup] = field(default_factory=list)
    generated_files: list[Path] = field(default_factory=list)
    emails_sent: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewPair:
    article_a: str
    article_b: str
    score: float
    source: str
