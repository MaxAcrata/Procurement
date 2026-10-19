"""Comparison logic for orders vs invoices."""

from __future__ import annotations

import logging
import math

from core.article_match import ArticleConfig, calculate_score, classify
from models import ComparisonItem, Product, ReviewPair, SupplierMatchStatus

logger = logging.getLogger(__name__)


def compare_tables(
    order_products: list[Product],
    invoice_products: list[Product],
    config: ArticleConfig | None = None,
    review_pairs: list[ReviewPair] | None = None,
) -> list[ComparisonItem]:
    """Compare order items against invoice items using multi-level article scoring."""
    results: list[ComparisonItem] = []
    matched_invoice: set[int] = set()
    matched_order: set[int] = set()
    threshold = (config or ArticleConfig()).threshold

    # Highest-score pairs first so near-duplicate SKUs cannot be mis-assigned
    # by first-come order-row greedy matching.
    candidates: list[tuple[float, int, int]] = []
    for oi, order_item in enumerate(order_products):
        for ii, inv_item in enumerate(invoice_products):
            score = calculate_score(order_item.article, inv_item.article, config)
            if score >= threshold:
                candidates.append((score, oi, ii))
            elif review_pairs is not None and classify(score, config) == "review":
                review_pairs.append(
                    ReviewPair(
                        article_a=order_item.article,
                        article_b=inv_item.article,
                        score=score,
                        source="comparator",
                    )
                )
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))

    pairing: dict[int, int] = {}
    for _score, oi, ii in candidates:
        if oi in matched_order or ii in matched_invoice:
            continue
        matched_order.add(oi)
        matched_invoice.add(ii)
        pairing[oi] = ii

    for oi, order_item in enumerate(order_products):
        if oi in pairing:
            inv_item = invoice_products[pairing[oi]]

            if math.isclose(order_item.quantity, inv_item.quantity, abs_tol=1e-6):
                status = SupplierMatchStatus.OK
                diff = 0.0
            else:
                status = SupplierMatchStatus.MISMATCH_QUANTITY
                diff = inv_item.quantity - order_item.quantity

            results.append(
                ComparisonItem(
                    product=order_item,
                    invoice_article=inv_item.article,
                    invoice_quantity=inv_item.quantity,
                    status=status,
                    diff=diff,
                )
            )
        else:
            results.append(
                ComparisonItem(
                    product=order_item,
                    invoice_quantity=None,
                    status=SupplierMatchStatus.MISSING,
                )
            )

    for i, inv_item in enumerate(invoice_products):
        if i not in matched_invoice:
            results.append(
                ComparisonItem(
                    product=inv_item,
                    invoice_quantity=inv_item.quantity,
                    status=SupplierMatchStatus.EXTRA,
                )
            )

    logger.info(
        "Comparison done: %d order items vs %d invoice items → %d results",
        len(order_products),
        len(invoice_products),
        len(results),
    )
    return results


def get_comparison_summary(results: list[ComparisonItem]) -> dict[str, int | float]:
    """Generate summary statistics from comparison results."""
    total = len(results)
    if total == 0:
        return {"total": 0, "match_pct": 0.0, "ok": 0, "mismatches": 0, "missing": 0, "extra": 0}

    ok_count = sum(1 for r in results if r.status == SupplierMatchStatus.OK)
    mismatch_count = sum(1 for r in results if r.status == SupplierMatchStatus.MISMATCH_QUANTITY)
    missing_count = sum(1 for r in results if r.status == SupplierMatchStatus.MISSING)
    extra_count = sum(1 for r in results if r.status == SupplierMatchStatus.EXTRA)

    return {
        "total": total,
        "match_pct": round(ok_count / total * 100, 1),
        "ok": ok_count,
        "mismatches": mismatch_count,
        "missing": missing_count,
        "extra": extra_count,
    }
