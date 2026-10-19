"""OCR confidence flags (S2)."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from config import settings
from models import Product


class _FakeImg:
    size = (100, 50)
    format = "PNG"


def _install_fake_ocr(monkeypatch, confs, texts):
    """Stub pytesseract + PIL in sys.modules (works whether or not they're installed)."""
    fake_pt = ModuleType("pytesseract")
    fake_pt.Output = SimpleNamespace(DICT="dict")
    fake_pt.image_to_data = lambda img, lang=None, output_type=None: {"text": texts, "conf": confs}
    fake_pil = ModuleType("PIL")
    fake_image = ModuleType("PIL.Image")
    fake_image.open = lambda p: _FakeImg()
    fake_pil.Image = fake_image
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pt)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image)


def test_parse_image_sets_ocr_confidence_from_word_conf_mean(monkeypatch, tmp_path):
    from parsers.image_parser import parse_image

    _install_fake_ocr(
        monkeypatch,
        confs=["95", "80", "40"],
        texts=["Петля", "артикул:71B3750", "кол-во:10"],
    )
    f = tmp_path / "scan.png"
    f.write_bytes(b"png")

    result = parse_image(f)

    assert result.products, f"expected at least one product, raw_text={result.raw_text!r}"
    for p in result.products:
        assert p.ocr_confidence is not None
        assert abs(p.ocr_confidence - (95 + 80 + 40) / 3) < 0.01
    assert not any("низким OCR-confidence" in e for e in result.errors)  # 71.67 >= 70


def test_parse_image_warns_when_mean_below_threshold(monkeypatch, tmp_path):
    from parsers.image_parser import parse_image

    _install_fake_ocr(
        monkeypatch,
        confs=["40", "30", "35"],
        texts=["Петля", "Артикул:ABC123", "Кол-во:5"],
    )
    f = tmp_path / "bad.png"
    f.write_bytes(b"png")

    result = parse_image(f)

    assert result.products, f"expected products, raw_text={result.raw_text!r}"
    assert any("низким OCR-confidence" in e for e in result.errors)
    assert result.products[0].ocr_confidence == 35.0


def test_normalize_preserves_unit_and_ocr_confidence():
    from core.normalizer import normalize_data

    p = Product(name="Петля", article="71B3750", quantity=1.0, supplier="Blum", unit="шт", ocr_confidence=42.0)
    out = normalize_data([p])
    assert out and out[0].unit == "шт"
    assert out[0].ocr_confidence == 42.0


def test_ocr_threshold_config_exists():
    assert settings.ocr.low_confidence_threshold == 70.0


def test_parsed_data_page_highlights_low_confidence_rows():
    from PySide6.QtWidgets import QApplication

    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.parsed_data_vm import ParsedDataViewModel
    from gui.views.parsed_data_page import ParsedDataPage

    QApplication.instance() or QApplication([])

    backend = ProcurementBackend()
    backend._products = [
        Product(name="Good", article="ABC-1", quantity=1.0, supplier="S", ocr_confidence=95.0),
        Product(name="Bad", article="ABC-2", quantity=1.0, supplier="S", ocr_confidence=30.0),
    ]
    vm = ParsedDataViewModel(backend)
    vm.refresh()
    page = ParsedDataPage(vm)
    page._filter_data()

    assert page.table.rowCount() == 2
    good_bg = page.table.item(0, 0).background().color().name()
    bad_bg = page.table.item(1, 0).background().color().name()
    assert bad_bg != good_bg, "low-confidence row must be highlighted"
