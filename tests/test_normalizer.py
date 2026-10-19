"""Unit tests for normalizer module."""

from models import Product
from core.normalizer import (
    _normalize_article,
    _normalize_name,
    _normalize_supplier,
    _validate_article,
    _make_key,
    normalize_data,
)


class TestNormalizeArticle:
    """Tests for article normalization."""

    def test_preserves_full_sku(self):
        assert _normalize_article("RT110GR.1/000/600") == "RT110GR.1/000/600"

    def test_preserves_dots(self):
        assert _normalize_article("70.1503.BP") == "70.1503.BP"

    def test_preserves_slashes(self):
        assert _normalize_article("MHB.C07.BV.1L.10") == "MHB.C07.BV.1L.10"

    def test_preserves_dashes(self):
        assert _normalize_article("ABC-123/45") == "ABC-123/45"

    def test_preserves_mixed(self):
        assert _normalize_article("TN50.10-B") == "TN50.10-B"

    def test_trim_whitespace(self):
        assert _normalize_article("  ABC-123  ") == "ABC-123"

    def test_remove_internal_spaces(self):
        assert _normalize_article("2574 20") == "257420"

    def test_uppercase(self):
        assert _normalize_article("abc-123") == "ABC-123"

    def test_empty_string(self):
        assert _normalize_article("") == ""

    def test_none_returns_empty(self):
        assert _normalize_article(None) == ""

    def test_non_breaking_space(self):
        assert _normalize_article("ABC\xa0123") == "ABC123"

    def test_different_articles_stay_different(self):
        a1 = _normalize_article("RT110GR.1/000/600")
        a2 = _normalize_article("RT110GR.1/128/150")
        assert a1 != a2
        assert a1 == "RT110GR.1/000/600"
        assert a2 == "RT110GR.1/128/150"


class TestValidateArticle:
    """Tests for article validation."""

    def test_valid_article(self):
        assert _validate_article("ABC-123") is True

    def test_too_short(self):
        assert _validate_article("AB") is False

    def test_no_letters(self):
        assert _validate_article("12345") is False

    def test_no_digits(self):
        assert _validate_article("ABCDE") is False

    def test_exactly_5_chars(self):
        assert _validate_article("AB123") is True

    def test_empty(self):
        assert _validate_article("") is False


class TestMakeKey:
    """Tests for deduplication key."""

    def test_same_product_same_key(self):
        p1 = Product(name="Test", article="ABC-123", quantity=1, supplier="BLUM")
        p2 = Product(name="Test", article="ABC-123", quantity=2, supplier="BLUM")
        assert _make_key(p1) == _make_key(p2)

    def test_different_article_different_key(self):
        p1 = Product(name="Test", article="RT110GR.1/000/600", quantity=1, supplier="BLUM")
        p2 = Product(name="Test", article="RT110GR.1/128/150", quantity=1, supplier="BLUM")
        assert _make_key(p1) != _make_key(p2)

    def test_different_supplier_different_key(self):
        p1 = Product(name="Test", article="ABC-123", quantity=1, supplier="BLUM")
        p2 = Product(name="Test", article="ABC-123", quantity=1, supplier="МДМ")
        assert _make_key(p1) != _make_key(p2)

    def test_case_insensitive(self):
        p1 = Product(name="test", article="abc-123", quantity=1, supplier="blum")
        p2 = Product(name="TEST", article="ABC-123", quantity=1, supplier="BLUM")
        assert _make_key(p1) == _make_key(p2)


class TestNormalizeData:
    """Tests for full normalization pipeline."""

    def test_different_articles_not_merged(self):
        products = [
            Product(name="Ручка", article="RT110GR.1/000/600", quantity=2, supplier="BLUM"),
            Product(name="Ручка", article="RT110GR.1/128/150", quantity=3, supplier="BLUM"),
        ]
        result = normalize_data(products)
        assert len(result) == 2
        articles = {p.article for p in result}
        assert "RT110GR.1/000/600" in articles
        assert "RT110GR.1/128/150" in articles

    def test_same_article_merged(self):
        products = [
            Product(name="Ручка", article="ABC-123", quantity=2, supplier="BLUM"),
            Product(name="Ручка", article="ABC-123", quantity=3, supplier="BLUM"),
        ]
        result = normalize_data(products)
        assert len(result) == 1
        assert result[0].quantity == 5

    def test_different_suppliers_not_merged(self):
        products = [
            Product(name="Ручка", article="ABC-123", quantity=2, supplier="BLUM"),
            Product(name="Ручка", article="ABC-123", quantity=3, supplier="МДМ"),
        ]
        result = normalize_data(products)
        assert len(result) == 2

    def test_empty_input(self):
        assert normalize_data([]) == []

    def test_real_scenario(self):
        products = [
            Product(name="Ножка врезная 32мм", article="RT110GR.1/000/600", quantity=2, supplier="BLUM"),
            Product(name="Ножка врезная 32мм", article="RT110GR.1/128/150", quantity=3, supplier="BLUM"),
        ]
        result = normalize_data(products)
        assert len(result) == 2
        qties = {p.article: p.quantity for p in result}
        assert qties["RT110GR.1/000/600"] == 2
        assert qties["RT110GR.1/128/150"] == 3

    def test_normalize_name_ocr_fixes(self):
        # OCR fix map replaces doubled Cyrillic with Latin equivalents
        assert _normalize_name("ТТест") == "TTест"
        assert _normalize_name("ННормальный") == "HHормальный"

    def test_normalize_supplier_legal_forms(self):
        assert _normalize_supplier("ооо Ромашка") == "ООО Ромашка"
        assert _normalize_supplier("зао Тест") == "ЗАО Тест"
        assert _normalize_supplier("UNKNOWN") == "UNKNOWN"
        assert _normalize_supplier("") == "UNKNOWN"
