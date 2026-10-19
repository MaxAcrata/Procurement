"""Tests for order vs invoice comparison."""

from models import Product, SupplierMatchStatus
from core.comparator import compare_tables, get_comparison_summary


class TestCompareTables:
    def test_exact_match(self):
        order = [Product(name="Ручка", article="PEN-001", quantity=10)]
        invoice = [Product(name="Ручка", article="PEN-001", quantity=10)]
        results = compare_tables(order, invoice)
        assert len(results) == 1
        assert results[0].status == SupplierMatchStatus.OK

    def test_quantity_mismatch(self):
        order = [Product(name="Ручка", article="PEN-001", quantity=10)]
        invoice = [Product(name="Ручка", article="PEN-001", quantity=15)]
        results = compare_tables(order, invoice)
        assert len(results) == 1
        assert results[0].status == SupplierMatchStatus.MISMATCH_QUANTITY
        assert results[0].diff == 5.0

    def test_missing_in_invoice(self):
        order = [Product(name="Ручка", article="PEN-001", quantity=10)]
        invoice = []
        results = compare_tables(order, invoice)
        assert len(results) == 1
        assert results[0].status == SupplierMatchStatus.MISSING

    def test_extra_in_invoice(self):
        order = []
        invoice = [Product(name="Ручка", article="PEN-001", quantity=10)]
        results = compare_tables(order, invoice)
        assert len(results) == 1
        assert results[0].status == SupplierMatchStatus.EXTRA

    def test_mixed_results(self):
        order = [
            Product(name="Ручка", article="PEN-001", quantity=10),
            Product(name="Степлер", article="STAP-10", quantity=5),
        ]
        invoice = [
            Product(name="Ручка", article="PEN-001", quantity=10),
            Product(name="Маркер", article="MARK-01", quantity=3),
        ]
        results = compare_tables(order, invoice)
        assert len(results) == 3  # 1 OK + 1 MISSING + 1 EXTRA

    def test_both_empty(self):
        results = compare_tables([], [])
        assert results == []


class TestComparisonSummary:
    def test_empty_results(self):
        summary = get_comparison_summary([])
        assert summary["total"] == 0
        assert summary["ok"] == 0

    def test_all_ok(self):
        from models import ComparisonItem
        results = [
            ComparisonItem(product=Product("A", "A1", 1), status=SupplierMatchStatus.OK),
            ComparisonItem(product=Product("B", "B1", 1), status=SupplierMatchStatus.OK),
        ]
        summary = get_comparison_summary(results)
        assert summary["total"] == 2
        assert summary["ok"] == 2
        assert summary["match_pct"] == 100.0

    def test_mixed(self):
        from models import ComparisonItem
        results = [
            ComparisonItem(product=Product("A", "A1", 1), status=SupplierMatchStatus.OK),
            ComparisonItem(product=Product("B", "B1", 1), status=SupplierMatchStatus.MISSING),
            ComparisonItem(product=Product("C", "C1", 1), status=SupplierMatchStatus.EXTRA),
        ]
        summary = get_comparison_summary(results)
        assert summary["total"] == 3
        assert summary["ok"] == 1
        assert summary["missing"] == 1
        assert summary["extra"] == 1
        assert summary["match_pct"] == 33.3
