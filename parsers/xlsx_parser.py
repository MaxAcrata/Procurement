"""Universal XLSX parser — handles files with and without headers."""

from __future__ import annotations

import logging
from pathlib import Path

from models import DocumentParseResult, Product
from parsers.utils import map_columns_by_keywords, parse_quantity

logger = logging.getLogger(__name__)

# Majority of sampled cells must match before a column is classified.
CONTENT_HEURISTIC_LONG_NAME_RATIO = 0.5
# Few known-supplier hits in a sample are already enough to flag the column.
SHORT_TOKEN_RATIO = 0.2
KNOWN_SUPPLIERS = [
    "blum",
    "hettich",
    "hafele",
    "grass",
    "camar",
    "ebco",
    "мдм",
    "макмарт",
    "ikea",
    "леруа",
    "petroff",
    "axor",
]
KNOWN_UNITS = ["шт", "компл", "штук", "кг", "упак", "пар", "рулон", "короб"]


def parse_xlsx(file_path: Path) -> DocumentParseResult:
    """Extract product data from an Excel file.

    Three column-detection strategies:
    1. Header keywords (Наименование, Артикул, Количество, Поставщик)
    2. Content analysis (numeric/alpha/uppercase patterns)
    3. Position fallback (col 0=name, 1=article, 2=quantity)
    """
    try:
        import pandas as pd
    except ImportError:
        return DocumentParseResult(
            file_path=file_path,
            file_type="xlsx",
            products=[],
            errors=["pandas not installed"],
        )

    products: list[Product] = []
    errors: list[str] = []

    try:
        sheets = pd.read_excel(str(file_path), sheet_name=None, engine="openpyxl", header=None)
        for _sheet_name, df in sheets.items():
            if df.empty or len(df) < 1:
                continue
            products.extend(_parse_sheet(df))
    except Exception as e:
        logger.exception("XLSX parse error for %s", file_path)
        errors.append(f"XLSX parse error: {e}")

    return DocumentParseResult(
        file_path=file_path,
        file_type="xlsx",
        products=products,
        errors=errors,
    )


# ── Sheet-level strategies ───────────────────────────────────────────────────


def _parse_sheet(df) -> list[Product]:
    first_row = [str(c).lower().strip() if c else "" for c in df.iloc[0]]
    header_map = map_columns_by_keywords(first_row)
    if header_map and len(header_map) >= 2:
        return _parse_rows(df.iloc[1:].reset_index(drop=True), header_map)

    col_map = _analyze_column_types(df)
    if col_map:
        return _parse_rows(df, col_map)

    return _parse_rows(df, _position_fallback(df))


def _parse_rows(df, col_map: dict[str, int]) -> list[Product]:
    products: list[Product] = []
    for _, row in df.iterrows():
        product = _extract_product(row, col_map)
        if product:
            products.append(product)
    return products


# ── Column type analysis ─────────────────────────────────────────────────────


def _analyze_column_types(df) -> dict[str, int]:
    result: dict[str, int] = {}

    # Pass 1: numeric → quantity
    for col_idx in range(len(df.columns)):
        sample = _sample_strings(df, col_idx)
        if not sample:
            continue
        numeric_count = sum(1 for s in sample if _is_numeric(s))
        if numeric_count >= len(sample) * CONTENT_HEURISTIC_LONG_NAME_RATIO and "quantity" not in result:
            result["quantity"] = col_idx

    # Skip unit columns
    unit_cols = set()
    for col_idx in range(len(df.columns)):
        if col_idx in result.values():
            continue
        sample = _sample_strings(df, col_idx)
        if sample and _is_unit_column(sample):
            unit_cols.add(col_idx)

    # Pass 2: name (longest average text)
    for col_idx in range(len(df.columns)):
        if col_idx in result.values() or col_idx in unit_cols:
            continue
        sample = _sample_strings(df, col_idx)
        if not sample:
            continue
        avg_len = sum(len(s) for s in sample) / len(sample)
        if avg_len >= 10 and "name" not in result:
            result["name"] = col_idx

    # Pass 3: supplier (known names / all uppercase)
    for col_idx in range(len(df.columns)):
        if col_idx in result.values() or col_idx in unit_cols:
            continue
        sample = _sample_strings(df, col_idx)
        if sample and _is_supplier_column(sample) and "supplier" not in result:
            result["supplier"] = col_idx

    # Pass 4: article (remaining short alphanumeric with digits)
    for col_idx in range(len(df.columns)):
        if col_idx in result.values() or col_idx in unit_cols:
            continue
        sample = _sample_strings(df, col_idx)
        if sample and _is_article_column(sample) and "article" not in result:
            result["article"] = col_idx

    return result


def _sample_strings(df, col_idx: int, n: int = 10) -> list[str]:
    return [str(s).strip() for s in df[col_idx].dropna().head(n).tolist()]


def _position_fallback(df) -> dict[str, int]:
    col_map = _analyze_column_types(df)
    if col_map:
        return col_map

    n_cols = len(df.columns)
    base = {"name": 0, "article": 1, "quantity": 2}
    if n_cols >= 5:
        base["supplier"] = 4
    elif n_cols >= 4:
        sample = _sample_strings(df, 3, 5)
        if sample and not _is_unit_column(sample):
            base["supplier"] = 3
    return base


# ── Type detectors ───────────────────────────────────────────────────────────


def _is_numeric(s: str) -> bool:
    s = s.replace(" ", "").replace(",", ".").replace("\xa0", "")
    try:
        float(s)
        return True
    except ValueError:
        return False


def _is_unit_column(sample: list[str]) -> bool:
    matches = sum(1 for s in sample if any(u in s.lower() for u in KNOWN_UNITS))
    return matches >= len(sample) * CONTENT_HEURISTIC_LONG_NAME_RATIO


def _is_supplier_column(sample: list[str]) -> bool:
    matches = sum(1 for s in sample if any(k in s.lower() for k in KNOWN_SUPPLIERS))
    if matches >= len(sample) * SHORT_TOKEN_RATIO:
        return True
    upper_count = sum(1 for s in sample if s.isalpha() and s.isupper() and len(s) <= 20)
    return upper_count >= len(sample) * CONTENT_HEURISTIC_LONG_NAME_RATIO


def _is_article_column(sample: list[str]) -> bool:
    def looks_like_article(s: str) -> bool:
        if len(s) > 20 or len(s) < 2:
            return False
        return any(c.isdigit() for c in s) and any(c.isalpha() for c in s)

    matches = sum(1 for s in sample if looks_like_article(s))
    return matches >= len(sample) * CONTENT_HEURISTIC_LONG_NAME_RATIO


# ── Product extraction ───────────────────────────────────────────────────────


def _extract_product(row, col_map: dict[str, int]) -> Product | None:
    try:
        name_idx = col_map.get("name", 0)
        article_idx = col_map.get("article", 1)
        quantity_idx = col_map.get("quantity", 2)

        name = str(row.iloc[name_idx]).strip() if name_idx < len(row) else ""
        article = str(row.iloc[article_idx]).strip() if article_idx < len(row) else ""
        quantity = parse_quantity(row.iloc[quantity_idx] if quantity_idx < len(row) else 0)

        supplier = "UNKNOWN"
        if "supplier" in col_map:
            s_idx = col_map["supplier"]
            if s_idx < len(row):
                supplier = str(row.iloc[s_idx]).strip()

        unit = ""
        if "unit" in col_map:
            u_idx = col_map["unit"]
            if u_idx < len(row):
                unit = str(row.iloc[u_idx]).strip()

        if name and name not in ("nan", "None"):
            return Product(
                name=name,
                article=article if article not in ("nan", "None") else "",
                quantity=quantity,
                supplier=supplier if supplier and supplier not in ("nan", "None") else "UNKNOWN",
                unit=unit if unit and unit not in ("nan", "None") else "",
            )
    except (IndexError, ValueError, KeyError) as e:
        logger.warning("Skipping unparseable row %r: %s", row, e)
    return None
