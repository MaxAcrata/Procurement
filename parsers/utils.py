"""Shared utilities for document parsers — eliminates duplication."""

from __future__ import annotations

import logging
import re
from typing import Any

from models import Product

logger = logging.getLogger(__name__)

# ── Quantity parsing ─────────────────────────────────────────────────────────


def parse_quantity(value: Any) -> float:
    """Parse a quantity value from various formats (str, int, float)."""
    if value is None:
        return 0.0
    s = str(value).strip().replace(" ", "").replace(",", ".").replace("\xa0", "")
    try:
        return float(s)
    except ValueError:
        logger.warning("Unparseable quantity value: %r", value)
        return 0.0


# ── Column mapping ───────────────────────────────────────────────────────────

_KEYWORD_MAP: dict[str, list[str]] = {
    "name": ["наименование", "название", "товар", "name", "продукция", "описание"],
    "article": ["артикул", "код", "sku", "article", "номенклатура", "модель", "арт"],
    "quantity": ["количеств", "кол-во", "qty", "quantity", "штук", "объем"],
    "unit": ["ед.изм", "ед изм", "единиц", "unit", "ед"],
    "supplier": ["поставщик", "supplier", "vendor", "организация", "фирма", "магазин", "store"],
}


def map_columns_by_keywords(header: list[str]) -> dict[str, int]:
    """Map column names to indices by keyword matching (case-insensitive, substring)."""
    result: dict[str, int] = {}
    for i, cell in enumerate(header):
        cell_lower = cell.lower()
        for field_name, keywords in _KEYWORD_MAP.items():
            if field_name in result:
                continue
            for kw in keywords:
                if kw in cell_lower:
                    result[field_name] = i
                    break
    return result


# ── Text-based product extraction ────────────────────────────────────────────

_TEXT_PATTERN = re.compile(
    r"^(.+?)\s+(?:артикул|код|sku)[:\s]+(\S+)\s+(?:количеств|кол-во|qty)[:\s]+([\d.,]+)",
    re.IGNORECASE | re.MULTILINE,
)


def extract_products_from_text(text: str) -> list[Product]:
    """Extract products from unstructured text via regex."""
    products: list[Product] = []
    for match in _TEXT_PATTERN.finditer(text):
        name = match.group(1).strip()
        article = match.group(2).strip()
        quantity_str = match.group(3).replace(",", ".")
        try:
            quantity = float(quantity_str)
        except ValueError:
            logger.warning("Unparseable quantity value: %r", quantity_str)
            quantity = 0.0
        products.append(Product(name=name, article=article, quantity=quantity))
    return products
