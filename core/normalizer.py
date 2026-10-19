"""Data normalization and deduplication."""

from __future__ import annotations

import re
import logging

from models import Product, ReviewPair
from core.article_match import calculate_score, classify, compare_articles, ArticleConfig

logger = logging.getLogger(__name__)

# OCR double-letter fix map
_OCR_FIXES: dict[str, str] = {
    "ОО": "OO", "ЛЛ": "LL", "НН": "HH", "ММ": "MM",
    "ТТ": "TT", "РР": "PP", "ВВ": "BB", "АА": "AA",
}

# Russian legal-form abbreviations
_LEGAL_FORMS: dict[str, str] = {
    "ооо": "ООО", "зао": "ЗАО", "пао": "ПАО", "ао": "АО", "ип": "ИП",
}


def normalize_data(
    products: list[Product],
    review_pairs: list[ReviewPair] | None = None,
    config: ArticleConfig | None = None,
) -> list[Product]:
    """Normalize and deduplicate product data.

    1. Clean text (strip, normalize whitespace)
    2. Fix OCR errors
    3. Normalize article (preserve full SKU)
    4. Normalize supplier names
    5. Deduplicate by article matching
    """
    if not products:
        return []

    cleaned: list[Product] = []
    for p in products:
        product = Product(
            name=_normalize_name(p.name),
            article=_normalize_article(p.article),
            quantity=p.quantity,
            supplier=_normalize_supplier(p.supplier),
            unit=p.unit,
            ocr_confidence=p.ocr_confidence,
        )
        if product.name:
            cleaned.append(product)

    return _merge_duplicates(cleaned, config=config, review_pairs=review_pairs)


# ── Individual normalizers ───────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    name = re.sub(r"\s+", " ", name)
    for wrong, right in _OCR_FIXES.items():
        name = name.replace(wrong, right)
    return name


def _normalize_article(article: str) -> str:
    """Normalize article: trim, remove spaces/non-breaking spaces, uppercase.

    Preserves ALL characters (dots, slashes, dashes) — no splitting or truncation.
    """
    if not article:
        return ""
    article = article.strip().replace(" ", "").replace("\xa0", "")
    return article.upper()


def _validate_article(article: str) -> bool:
    """Validate article: must be >= 3 chars, contain both letters and digits."""
    if not article or len(article) < 3:
        return False
    return any(c.isalpha() for c in article) and any(c.isdigit() for c in article)


def _make_key(product: Product) -> str:
    """Generate a deduplication key from supplier + normalized article."""
    return f"{product.supplier.upper()}|{_normalize_article(product.article)}"


def _normalize_supplier(supplier: str) -> str:
    if not supplier or supplier == "UNKNOWN":
        return "UNKNOWN"

    supplier = supplier.strip()
    supplier = re.sub(r"\s+", " ", supplier)

    supplier_lower = supplier.lower()
    for abbr, full in _LEGAL_FORMS.items():
        if supplier_lower.startswith(abbr + " ") or supplier_lower.startswith(abbr + "\n"):
            supplier = full + supplier[len(abbr):]
            break

    return supplier


# ── Deduplication ────────────────────────────────────────────────────────────

def _merge_duplicates(
    products: list[Product],
    config: ArticleConfig | None = None,
    review_pairs: list[ReviewPair] | None = None,
) -> list[Product]:
    """Merge duplicate products using multi-level article matching.

    Groups by supplier first, then matches articles within each group.
    """
    if not products:
        return []

    supplier_groups: dict[str, list[Product]] = {}
    for p in products:
        key = p.supplier.upper()
        supplier_groups.setdefault(key, []).append(p)

    merged: list[Product] = []

    for supplier, group in supplier_groups.items():
        used: set[int] = set()

        for i, p1 in enumerate(group):
            if i in used:
                continue

            match_group = [p1]
            for j, p2 in enumerate(group[i + 1:], start=i + 1):
                if j in used:
                    continue
                score = calculate_score(p1.article, p2.article, config)
                if score >= (config or ArticleConfig()).threshold:
                    match_group.append(p2)
                    used.add(j)
                elif review_pairs is not None and classify(score, config) == "review":
                    review_pairs.append(ReviewPair(
                        article_a=p1.article,
                        article_b=p2.article,
                        score=score,
                        source="normalizer",
                    ))

            merged_product = Product(
                name=match_group[0].name,
                article=match_group[0].article,
                quantity=sum(p.quantity for p in match_group),
                supplier=supplier if supplier != "UNKNOWN" else (
                    next((p.supplier for p in match_group if p.supplier != "UNKNOWN"), "UNKNOWN")
                ),
                unit=next((p.unit for p in match_group if p.unit), ""),
                ocr_confidence=min(
                    (p.ocr_confidence for p in match_group if p.ocr_confidence is not None),
                    default=None,
                ),
            )
            merged.append(merged_product)

    return merged
