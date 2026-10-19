"""P2 UX fixes.

P2-19a: "Сравнить" with no files selected must show a visible message, not no-op.
P2-19b: process_files must return "success" with count 0 for clean-but-empty
        input; "error" only when parse errors are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from models import DocumentParseResult


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ── P2-19b: process_files status contract ───────────────────────────────────


def test_process_files_empty_file_list_is_success():
    """No files → no parse errors → success with count 0, not error."""
    from gui.services.backend_impl import ProcurementBackend

    result = ProcurementBackend().process_files([])

    assert result["status"] == "success"
    assert result["count"] == 0
    assert result["errors"] == []


def test_process_files_no_products_no_errors_is_success(monkeypatch):
    """Legitimately clean-but-empty input must not be reported as error."""
    from gui.services import backend_impl

    def fake_parse(file_path):
        return DocumentParseResult(file_path=Path(file_path), file_type="xlsx", products=[], errors=[])

    monkeypatch.setattr(backend_impl, "parse_document", fake_parse)

    result = backend_impl.ProcurementBackend().process_files([Path("clean_empty.xlsx")])

    assert result["status"] == "success"
    assert result["count"] == 0
    assert result["errors"] == []


def test_process_files_parse_errors_is_error(monkeypatch):
    """Parse errors present → status error, errors propagated."""
    from gui.services import backend_impl

    def fake_parse(file_path):
        return DocumentParseResult(
            file_path=Path(file_path),
            file_type="xlsx",
            products=[],
            errors=["bad header"],
        )

    monkeypatch.setattr(backend_impl, "parse_document", fake_parse)

    result = backend_impl.ProcurementBackend().process_files([Path("broken.xlsx")])

    assert result["status"] == "error"
    assert result["errors"] == ["bad header"]


# ── P2-19a: compare with no files selected must show a message ──────────────


class _DummyBackend:
    def compare(self, order_path, invoice_paths):
        return []


def test_compare_with_no_files_shows_status_message(qapp):
    from gui.viewmodels.comparison_vm import ComparisonViewModel
    from gui.views.comparison_page import ComparisonPage

    page = ComparisonPage(ComparisonViewModel(_DummyBackend()))
    page._compare()

    assert page.status_label.text().strip() != ""
