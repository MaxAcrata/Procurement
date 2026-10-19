"""Tests for shared parser utilities."""

from parsers.utils import parse_quantity, map_columns_by_keywords, extract_products_from_text


class TestParseQuantity:
    def test_integer(self):
        assert parse_quantity(10) == 10.0

    def test_float(self):
        assert parse_quantity(3.5) == 3.5

    def test_string_integer(self):
        assert parse_quantity("42") == 42.0

    def test_string_float_comma(self):
        assert parse_quantity("3,5") == 3.5

    def test_string_with_spaces(self):
        assert parse_quantity("1 000") == 1000.0

    def test_non_breaking_space(self):
        assert parse_quantity("1\xa0000") == 1000.0

    def test_none(self):
        assert parse_quantity(None) == 0.0

    def test_empty_string(self):
        assert parse_quantity("") == 0.0

    def test_non_numeric(self):
        assert parse_quantity("abc") == 0.0


class TestMapColumnsByKeywords:
    def test_russian_headers(self):
        header = ["Наименование", "Артикул", "Количество", "Поставщик"]
        result = map_columns_by_keywords(header)
        assert result["name"] == 0
        assert result["article"] == 1
        assert result["quantity"] == 2
        assert result["supplier"] == 3

    def test_english_headers(self):
        header = ["Name", "SKU", "Qty", "Vendor"]
        result = map_columns_by_keywords(header)
        assert result["name"] == 0
        assert result["article"] == 1
        assert result["quantity"] == 2
        assert result["supplier"] == 3

    def test_partial_headers(self):
        header = ["Товар", "Код", "Объем"]
        result = map_columns_by_keywords(header)
        assert result["name"] == 0
        assert result["article"] == 1
        assert result["quantity"] == 2

    def test_no_match(self):
        header = ["Col1", "Col2", "Col3"]
        result = map_columns_by_keywords(header)
        assert result == {}

    def test_empty_header(self):
        assert map_columns_by_keywords([]) == {}


class TestExtractProductsFromText:
    def test_single_line(self):
        text = "Бумага А4 Артикул:PAPER-A4 Кол-во:100"
        products = extract_products_from_text(text)
        assert len(products) == 1
        assert products[0].name == "Бумага А4"
        assert products[0].article == "PAPER-A4"
        assert products[0].quantity == 100.0

    def test_multiple_lines(self):
        text = (
            "Ручка Артикул:PEN-001 Кол-во:50\n"
            "Степлер Артикул:STAP-10 Кол-во:10"
        )
        products = extract_products_from_text(text)
        assert len(products) == 2

    def test_comma_quantity(self):
        text = "Товар Артикул:ABC Код:123 Кол-во:3,5"
        products = extract_products_from_text(text)
        assert len(products) == 1
        assert products[0].quantity == 3.5

    def test_no_match(self):
        text = "Просто текст без артикулов"
        assert extract_products_from_text(text) == []

    def test_empty_text(self):
        assert extract_products_from_text("") == []
