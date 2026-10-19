"""Tests for Excel generators."""

import tempfile
from pathlib import Path

from models import Product, SupplierGroup, ComparisonItem, SupplierMatchStatus
from generators.excel_gen import generate_purchase_order, generate_comparison_report, _safe_filename


class TestSafeFilename:
    def test_simple_name(self):
        assert _safe_filename("ООО Ромашка") == "ООО_Ромашка"

    def test_special_chars(self):
        result = _safe_filename("ООО \"Ромашка\" & Co.")
        assert "/" not in result
        assert "\\" not in result
        assert '"' not in result

    def test_empty(self):
        assert _safe_filename("") == "unknown"

    def test_unicode(self):
        result = _safe_filename("МДМ-Мебель")
        assert result == "МДМ-Мебель"


class TestGeneratePurchaseOrder:
    def test_creates_file(self):
        supplier = SupplierGroup(
            name="ООО Тест",
            products=[Product(name="Ручка", article="PEN-001", quantity=10)],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = generate_purchase_order(supplier, Path(tmpdir))
            assert filepath.exists()
            assert filepath.suffix == ".xlsx"
            assert "ООО_Тест" in filepath.name

    def test_empty_supplier(self):
        supplier = SupplierGroup(name="Пустой", products=[])
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = generate_purchase_order(supplier, Path(tmpdir))
            assert filepath.exists()


class TestGenerateComparisonReport:
    def test_creates_file(self):
        results = [
            ComparisonItem(
                product=Product(name="Ручка", article="PEN-001", quantity=10),
                invoice_quantity=10,
                status=SupplierMatchStatus.OK,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.xlsx"
            filepath = generate_comparison_report(results, output)
            assert filepath.exists()
            assert filepath.suffix == ".xlsx"

    def test_empty_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.xlsx"
            filepath = generate_comparison_report([], output)
            assert filepath.exists()
