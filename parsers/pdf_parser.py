"""PDF parser using pdfplumber."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from models import DocumentParseResult, Product
from parsers.utils import parse_quantity, map_columns_by_keywords, extract_products_from_text

logger = logging.getLogger(__name__)

_ARTICLE_RE = re.compile(r"([A-Z0-9][A-Z0-9./-]+[A-Z0-9])", re.IGNORECASE)


def parse_pdf(file_path: Path) -> DocumentParseResult:
    """Extract product data from a PDF file."""
    try:
        import pdfplumber
    except ImportError:
        return DocumentParseResult(
            file_path=file_path, file_type="pdf", products=[],
            errors=["pdfplumber not installed"],
        )

    products: list[Product] = []
    raw_text_parts: list[str] = []
    errors: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                raw_text_parts.append(text)

                for table in page.extract_tables():
                    if not table or len(table) < 2:
                        continue
                    header = [str(c).lower().strip() if c else "" for c in table[0]]
                    col_map = map_columns_by_keywords(header)
                    if not col_map:
                        continue

                    for row in table[1:]:
                        product = _row_to_product(row, col_map)
                        if product:
                            products.append(product)

        # Fallback: regex parsing from raw text when tables yield nothing
        if not products:
            raw_text = "\n".join(raw_text_parts)
            if raw_text.strip():
                products = extract_products_from_text(raw_text)
    except Exception as e:
        logger.exception("PDF parse error for %s", file_path)
        errors.append(f"PDF parse error: {e}")

    return DocumentParseResult(
        file_path=file_path, file_type="pdf", products=products,
        raw_text="\n".join(raw_text_parts), errors=errors,
    )


def _row_to_product(row: list, col_map: dict[str, int]) -> Product | None:
    try:
        name_idx = col_map.get("name", 0)
        article_idx = col_map.get("article", 1)
        quantity_idx = col_map.get("quantity", 2)
        supplier_idx = col_map.get("supplier")

        name = str(row[name_idx]).strip() if name_idx < len(row) and row[name_idx] else ""
        article_raw = str(row[article_idx]).strip() if article_idx < len(row) and row[article_idx] else ""

        # Clean article: collapse whitespace, extract main alphanumeric code
        article_raw = " ".join(article_raw.replace("\n", " ").replace("\r", "").split())
        m = _ARTICLE_RE.match(article_raw)
        article = m.group(1) if m else article_raw

        quantity = parse_quantity(row[quantity_idx] if quantity_idx < len(row) else 0)

        supplier = "UNKNOWN"
        if supplier_idx is not None and supplier_idx < len(row) and row[supplier_idx]:
            supplier = str(row[supplier_idx]).strip()

        if name:
            return Product(name=name, article=article, quantity=quantity, supplier=supplier)
    except (IndexError, ValueError) as e:
        logger.warning("Skipping unparseable row %r: %s", row, e)
    return None
