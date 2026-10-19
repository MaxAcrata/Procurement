"""Stability tests for parsers: skip logging, PDF text fallback, named constants."""

from __future__ import annotations

import logging

from parsers import xlsx_parser
from parsers.docx_parser import _row_to_product as docx_row_to_product
from parsers.pdf_parser import _row_to_product as pdf_row_to_product
from parsers.pdf_parser import parse_pdf
from parsers.utils import extract_products_from_text, parse_quantity

# ── fixtures / fakes ─────────────────────────────────────────────────────────


class _ExplodingIloc:
    def __getitem__(self, idx):
        raise ValueError("boom")


class _ExplodingRow:
    def __len__(self) -> int:
        return 3

    iloc = _ExplodingIloc()

    def __repr__(self) -> str:
        return "Row(BADROW)"


class _BadRow:
    def __len__(self) -> int:
        return 5

    def __getitem__(self, i):
        raise IndexError("boom")

    def __repr__(self) -> str:
        return "['BADROW']"


def _build_minimal_pdf(text_lines: list[str]) -> bytes:
    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    ops = []
    y = 720
    for line in text_lines:
        ops.append(f"BT /F1 12 Tf 40 {y} Td ({esc(line)}) Tj ET")
        y -= 18
    stream = "\n".join(ops).encode("ascii")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF").encode("ascii")
    return bytes(out)


# ── P2-12: silent row drops must log ─────────────────────────────────────────


def test_parse_quantity_logs_warning_on_unparseable_value(caplog):
    with caplog.at_level(logging.WARNING, logger="parsers.utils"):
        result = parse_quantity("abc")
    assert result == 0.0
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "abc" in caplog.text


def test_extract_products_from_text_logs_warning_on_unparseable_quantity(caplog):
    text = "Widget sku ABC123 qty 1.2.3"
    with caplog.at_level(logging.WARNING, logger="parsers.utils"):
        products = extract_products_from_text(text)
    assert len(products) == 1
    assert products[0].quantity == 0.0
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "1.2.3" in caplog.text


def test_xlsx_skipped_row_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="parsers.xlsx_parser"):
        product = xlsx_parser._extract_product(_ExplodingRow(), {"name": 0})
    assert product is None
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "BADROW" in caplog.text


def test_docx_skipped_row_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="parsers.docx_parser"):
        product = docx_row_to_product(["BADROW"], {"name": 0, "article": 5, "quantity": 2})
    assert product is None
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "BADROW" in caplog.text


def test_pdf_skipped_row_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="parsers.pdf_parser"):
        product = pdf_row_to_product(_BadRow(), {"name": 0, "article": 1, "quantity": 2})
    assert product is None
    assert any(r.levelno == logging.WARNING for r in caplog.records)
    assert "BADROW" in caplog.text


# ── P2-13: table-less PDF must fall back to text extraction ──────────────────


def test_pdf_tableless_document_falls_back_to_text(tmp_path):
    pdf_path = tmp_path / "tableless.pdf"
    pdf_path.write_bytes(
        _build_minimal_pdf(
            [
                "Bolts sku BOLT-01 qty 12",
                "Nuts sku NUT-02 qty 3",
            ]
        )
    )
    result = parse_pdf(pdf_path)
    assert result.errors == []
    assert len(result.products) == 2
    assert result.products[0].name == "Bolts"
    assert result.products[0].article == "BOLT-01"
    assert result.products[0].quantity == 12.0
    assert result.products[1].name == "Nuts"


# ── P2-14a: magic numbers/whitelists promoted to named constants ─────────────


def test_xlsx_exposes_named_heuristic_constants():
    assert xlsx_parser.CONTENT_HEURISTIC_LONG_NAME_RATIO == 0.5
    assert xlsx_parser.SHORT_TOKEN_RATIO == 0.2
    assert "blum" in xlsx_parser.KNOWN_SUPPLIERS
    assert "шт" in xlsx_parser.KNOWN_UNITS
