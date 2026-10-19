"""Regression tests for the two P0 email defects.

P0-1: GUI send_emails must call the mailer with the real generated order file
      (and must not report "sent" when it never sent anything).
P0-2: CLI --send-emails must attach the file generate_purchase_order actually
      wrote; send_purchase_order_email must not silently succeed without it.
"""

from __future__ import annotations

import json
from pathlib import Path

from models import Product, SupplierGroup, DocumentParseResult


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_backend_with_supplier():
    from gui.services.backend_impl import ProcurementBackend

    backend = ProcurementBackend()
    product = Product(name="Петля", article="71B3750", quantity=10.0, supplier="Blum")
    backend._products = [product]
    backend._suppliers = [SupplierGroup(name="Blum", products=[product])]
    backend._emails = {"Blum": "blum@example.com"}
    return backend


class _RecordingSender:
    def __init__(self, status: str = "success"):
        self.status = status
        self.calls: list[dict] = []

    def __call__(self, to, supplier_name, attachment_path, **kwargs):
        self.calls.append(
            {"to": to, "supplier_name": supplier_name, "attachment_path": Path(attachment_path)}
        )
        return {"status": self.status, "message": self.status}


# ── P0-1: GUI path ──────────────────────────────────────────────────────────

def test_gui_send_emails_calls_mailer_with_generated_attachment(tmp_path, monkeypatch):
    """After generate_orders, send must attach the real generated file."""
    from gui.services import backend_impl

    backend = _make_backend_with_supplier()
    generated = backend.generate_orders(tmp_path)
    assert generated, "generate_orders must produce at least one file"

    sender = _RecordingSender()
    monkeypatch.setattr(backend_impl, "send_purchase_order_email", sender, raising=False)

    results = backend.send_emails()

    assert len(sender.calls) == 1
    call = sender.calls[0]
    assert call["to"] == "blum@example.com"
    assert call["supplier_name"] == "Blum"
    assert call["attachment_path"] == generated[0]
    assert call["attachment_path"].exists()
    assert results == [{"supplier": "Blum", "email": "blum@example.com", "status": "sent"}]


def test_gui_send_emails_reports_real_mailer_status(tmp_path, monkeypatch):
    """A mailer failure must be reported as failure, never as sent."""
    from gui.services import backend_impl

    backend = _make_backend_with_supplier()
    backend.generate_orders(tmp_path)

    sender = _RecordingSender(status="error")
    monkeypatch.setattr(backend_impl, "send_purchase_order_email", sender, raising=False)

    results = backend.send_emails()

    assert results[0]["status"] == "error"
    assert results[0]["status"] != "sent"


def test_gui_send_emails_without_orders_reports_missing_file(monkeypatch):
    """No generated orders → honest no_order_file status, no fake send."""
    from gui.services import backend_impl

    backend = _make_backend_with_supplier()

    sender = _RecordingSender()
    monkeypatch.setattr(backend_impl, "send_purchase_order_email", sender, raising=False)

    results = backend.send_emails()

    assert sender.calls == []
    assert results == [{"supplier": "Blum", "status": "no_order_file"}]


def test_gui_send_emails_skips_suppliers_without_email(tmp_path, monkeypatch):
    """Suppliers without email get no_email and the mailer is not called for them."""
    from gui.services import backend_impl

    backend = _make_backend_with_supplier()
    backend._emails = {}
    backend.generate_orders(tmp_path)

    sender = _RecordingSender()
    monkeypatch.setattr(backend_impl, "send_purchase_order_email", sender, raising=False)

    results = backend.send_emails()

    assert sender.calls == []
    assert results == [{"supplier": "Blum", "status": "no_email"}]


# ── P0-2: attachment must exist, CLI must use the generated path ────────────

def test_send_purchase_order_email_errors_on_missing_attachment(tmp_path, monkeypatch):
    """Missing attachment → error status; SMTP must not be contacted."""
    import mailer.sender as sender_mod

    calls = []

    class _BoomSMTP:
        def __init__(self, *args, **kwargs):
            calls.append(args)
            raise AssertionError("SMTP must not be contacted without attachment")

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _BoomSMTP)

    missing = tmp_path / "does_not_exist.xlsx"
    result = sender_mod.send_purchase_order_email(
        to="blum@example.com",
        supplier_name="Blum",
        attachment_path=missing,
    )

    assert result["status"] == "error"
    assert "does_not_exist.xlsx" in result["message"]
    assert calls == []


def test_cli_process_send_emails_attaches_generated_file(tmp_path, monkeypatch):
    """--send-emails must attach the exact path generate_purchase_order returned."""
    import main as main_mod

    product = Product(name="Петля", article="71B3750", quantity=10.0, supplier="Blum")
    input_file = tmp_path / "in.xlsx"
    input_file.write_bytes(b"stub")
    parse_result = DocumentParseResult(
        file_path=input_file, file_type="xlsx", products=[product]
    )
    monkeypatch.setattr(main_mod, "parse_document", lambda p: parse_result)

    # Simulate the real naming scheme: <supplier>_<dd.mm.yyyy>.xlsx
    real_generated = tmp_path / "Blum_19.10.2026.xlsx"
    real_generated.write_bytes(b"stub")
    monkeypatch.setattr(
        main_mod, "generate_purchase_order", lambda sg, output_dir: real_generated
    )

    sender = _RecordingSender()
    monkeypatch.setattr("mailer.sender.send_purchase_order_email", sender)

    emails_db = tmp_path / "emails.json"
    emails_db.write_text(json.dumps({"Blum": "blum@example.com"}), encoding="utf-8")

    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        main_mod.app,
        [
            "process",
            str(tmp_path / "in.xlsx"),
            "--output-dir",
            str(tmp_path),
            "--send-emails",
            "--emails-db",
            str(emails_db),
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(sender.calls) == 1
    assert sender.calls[0]["attachment_path"] == real_generated
