"""Regression tests for two P2 stability defects.

P2-17: MIME header injection — attachment Content-Disposition filename must be
       sanitized (quotes / CR-LF / control chars) before embedding in headers.
P2-18: Comparator brittleness — quantity compare must tolerate float noise
       (math.isclose), and pairing must assign globally best-score pairs first
       instead of first-come greedy over order rows.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from models import Product, SupplierMatchStatus
from core.comparator import compare_tables
from core.article_match import ArticleConfig


# ── helpers ─────────────────────────────────────────────────────────────────

class _EvilPath:
    """Path-like whose .name is hostile but opens a real temp file.

    Windows filesystems cannot store quotes/CR/LF in filenames, so the name is
    faked while __fspath__ points at a real file for open()/exists().
    """

    def __init__(self, real: Path, name: str):
        self._real = real
        self.name = name

    def exists(self) -> bool:
        return self._real.exists()

    def __fspath__(self) -> str:
        return str(self._real)


class _CaptureSMTP:
    def __init__(self, *args, **kwargs):
        self.sent_msg = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, timeout=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        self.sent_msg = msg


def _send_with_attachment(tmp_path, monkeypatch, filename: str):
    """Call send_email with a hostile-named attachment; return captured message."""
    import mailer.sender as sender_mod

    real = tmp_path / "safe.xlsx"
    real.write_bytes(b"data")
    evil = _EvilPath(real, filename)

    captured = {}

    def _factory(*args, **kwargs):
        smtp = _CaptureSMTP()
        captured["smtp"] = smtp
        return smtp

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _factory)

    result = sender_mod.send_email(
        to="user@example.com",
        subject="s",
        body="b",
        attachments=[evil],
        smtp_user="user@example.com",
        smtp_password="secret",
    )
    return result, captured["smtp"].sent_msg


# ── P2-17: MIME header injection ────────────────────────────────────────────

def test_attachment_filename_with_quote_is_sanitized(tmp_path, monkeypatch):
    """A double quote in the filename must not break the quoted-string header."""
    result, msg = _send_with_attachment(tmp_path, monkeypatch, 'quote"file.xlsx')

    assert result["status"] == "success"
    part = next(p for p in msg.walk() if p.get_content_maintype() == "application")
    cd = part.get("Content-Disposition")
    # The filename value must not contain a raw unescaped quote.
    assert '"' not in cd.split("filename=", 1)[1].strip('"')
    assert "quote" in cd  # content preserved, only dangerous chars stripped


def test_attachment_filename_with_crlf_does_not_inject_or_crash(tmp_path, monkeypatch):
    """CR/LF in the filename must not inject headers nor raise HeaderParseError."""
    result, msg = _send_with_attachment(
        tmp_path, monkeypatch, 'crlf"\r\nX-Injected: pwned\r\n\r\n.xlsx'
    )

    assert result["status"] == "success"
    raw = msg.as_string()
    # The payload text may survive inside the filename, but must not become a header.
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    assert "\nX-Injected:" not in normalized
    assert "X-Injected" not in list(msg.keys())

    part = next(p for p in msg.walk() if p.get_content_maintype() == "application")
    cd = part.get("Content-Disposition")
    assert "\r" not in cd and "\n" not in cd


def test_normal_filename_header_unchanged(tmp_path, monkeypatch):
    """Ordinary filenames must keep the exact original header shape."""
    result, msg = _send_with_attachment(tmp_path, monkeypatch, "report.xlsx")

    assert result["status"] == "success"
    part = next(p for p in msg.walk() if p.get_content_maintype() == "application")
    assert part.get("Content-Disposition") == 'attachment; filename="report.xlsx"'


# ── P2-18a: quantity float tolerance ────────────────────────────────────────

def test_quantity_float_noise_is_ok_not_mismatch():
    """10.0 vs 10.0000001 must be OK — exact float equality is too strict."""
    order = [Product(name="Ручка", article="PEN-001", quantity=10.0)]
    invoice = [Product(name="Ручка", article="PEN-001", quantity=10.0000001)]
    results = compare_tables(order, invoice)
    assert len(results) == 1
    assert results[0].status == SupplierMatchStatus.OK
    assert results[0].diff == 0.0


def test_quantity_real_difference_still_mismatch():
    """A genuine quantity gap must still be reported as MISMATCH_QUANTITY."""
    order = [Product(name="Ручка", article="PEN-001", quantity=10.0)]
    invoice = [Product(name="Ручка", article="PEN-001", quantity=15.0)]
    results = compare_tables(order, invoice)
    assert results[0].status == SupplierMatchStatus.MISMATCH_QUANTITY
    assert results[0].diff == 5.0


# ── P2-18b: best-score-first pairing ────────────────────────────────────────

def test_pairing_prefers_globally_best_score_pair():
    """Near-duplicate SKUs: highest-score pair must win, not first order row.

    Order:  [ABCD-100, ABCD-101]
    Invoice:[ABCD-999, ABCD-101]
    Scores (threshold 0.4): O1-I1=0.457, O1-I2=0.486, O2-I1=0.457, O2-I2=1.0.
    First-come greedy lets O1 steal I2 (0.486), leaving O2 with I1 — wrong.
    Best-score-first assigns O2↔I2 (1.0) then O1↔I1.
    """
    cfg = ArticleConfig(threshold=0.4)
    order = [
        Product(name="Item1", article="ABCD-100", quantity=1.0),
        Product(name="Item2", article="ABCD-101", quantity=1.0),
    ]
    invoice = [
        Product(name="ItemA", article="ABCD-999", quantity=1.0),
        Product(name="ItemB", article="ABCD-101", quantity=1.0),
    ]
    results = compare_tables(order, invoice, config=cfg)

    by_article = {r.product.article: r for r in results if r.status != SupplierMatchStatus.EXTRA}
    # O2 (ABCD-101) must be paired with its exact match, not the leftover row.
    assert by_article["ABCD-101"].invoice_article == "ABCD-101"
    assert by_article["ABCD-101"].status == SupplierMatchStatus.OK
    # O1 gets the remaining above-threshold row.
    assert by_article["ABCD-100"].invoice_article == "ABCD-999"
    assert by_article["ABCD-100"].status == SupplierMatchStatus.OK
