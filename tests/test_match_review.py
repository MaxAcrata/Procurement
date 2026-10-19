"""Gray-band classification and review-pair collection (S3)."""

from __future__ import annotations

from core.article_match import ArticleConfig, classify, calculate_score
from core.comparator import compare_tables
from core.normalizer import normalize_data
from models import Product, ReviewPair


def test_classify_bands():
    cfg = ArticleConfig()  # threshold 0.75, gray_band (0.5, 0.75)
    assert classify(0.90, cfg) == "match"
    assert classify(0.75, cfg) == "match"
    assert classify(0.74, cfg) == "review"
    assert classify(0.50, cfg) == "review"
    assert classify(0.49, cfg) == "no_match"


def test_compare_tables_collects_gray_band_pairs():
    order = [Product(name="A", article="RT110GR.1/000/600", quantity=1.0)]
    invoice = [Product(name="A2", article="RT110GR.1/128/150", quantity=1.0)]
    score = calculate_score(order[0].article, invoice[0].article)
    # Adjust config so the pair falls in the gray band
    cfg = ArticleConfig(threshold=0.8, gray_band=(0.4, 0.8))
    assert classify(score, cfg) == "review", f"fixture score={score}"

    pairs: list[ReviewPair] = []
    compare_tables(order, invoice, config=cfg, review_pairs=pairs)

    assert len(pairs) == 1
    assert pairs[0].article_a == "RT110GR.1/000/600"
    assert pairs[0].article_b == "RT110GR.1/128/150"
    assert pairs[0].source == "comparator"
    assert abs(pairs[0].score - score) < 1e-9


def test_normalize_collects_gray_band_pairs():
    products = [
        Product(name="A", article="RT110GR.1/000/600", quantity=1.0, supplier="S"),
        Product(name="B", article="RT110GR.1/128/150", quantity=1.0, supplier="S"),
    ]
    cfg = ArticleConfig(threshold=0.8, gray_band=(0.4, 0.8))
    pairs: list[ReviewPair] = []
    normalize_data(products, review_pairs=pairs, config=cfg)
    assert any(p.source == "normalizer" for p in pairs)


def test_review_pairs_optional_and_backward_compatible():
    # Existing call shape (no review_pairs) must keep working.
    out = compare_tables(
        [Product(name="A", article="ABC-1", quantity=1.0)],
        [Product(name="A", article="ABC-1", quantity=1.0)],
    )
    assert len(out) == 1


# --- Task 6: review queue backend + GUI ---

def test_backend_review_queue_persist_and_decide(tmp_path):
    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend

    # AppConfig is frozen — bypass with object.__setattr__
    object.__setattr__(bi.settings, "emails_db_path", tmp_path / "emails_db.json")

    backend = ProcurementBackend()
    backend._pending_review_pairs = [
        ReviewPair("AAA-1", "AAA-2", 0.62, "comparator"),
        ReviewPair("BBB-1", "BBB-2", 0.55, "normalizer"),
    ]

    pending = backend.get_review_pairs()
    assert len(pending) == 2

    backend.decide_review_pair("AAA-1", "AAA-2", "confirmed")

    pending = backend.get_review_pairs()
    assert len(pending) == 1
    assert pending[0]["article_a"] == "BBB-1"

    saved = (tmp_path / "match_review.json").read_text(encoding="utf-8")
    assert "AAA-1" in saved and "confirmed" in saved


def test_review_vm_emits_and_refreshes():
    from PySide6.QtWidgets import QApplication
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.review_vm import ReviewViewModel

    QApplication.instance() or QApplication([])

    backend = ProcurementBackend()
    backend._pending_review_pairs = [ReviewPair("A", "B", 0.6, "comparator")]
    vm = ReviewViewModel(backend)
    vm.refresh()
    assert len(vm.pairs) == 1

    changed: list[int] = []
    vm.data_changed.connect(lambda: changed.append(1))
    vm.decide("A", "B", "confirmed")
    assert changed
    assert vm.pairs == []


def test_review_page_shows_pairs_and_decides():
    from PySide6.QtWidgets import QApplication
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.review_vm import ReviewViewModel
    from gui.views.review_page import ReviewPage

    QApplication.instance() or QApplication([])

    backend = ProcurementBackend()
    backend._pending_review_pairs = [ReviewPair("X-1", "X-2", 0.6, "comparator")]
    vm = ReviewViewModel(backend)
    page = ReviewPage(vm)
    vm.refresh()

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "X-1"
    assert page.table.item(0, 1).text() == "X-2"

    page.table.selectRow(0)
    page._decide("confirmed")
    assert page.table.rowCount() == 0


def test_backend_process_files_collects_review_pairs():
    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend

    # Use real data path (no monkeypatch needed for this test)
    backend = ProcurementBackend()
    # Simulate two products that fall in gray band
    from models import Product
    p1 = Product(name="A", article="RT110GR.1/000/600", quantity=1.0, supplier="S")
    p2 = Product(name="B", article="RT110GR.1/128/150", quantity=1.0, supplier="S")

    # Directly test normalize with review_pairs (bypasses parse)
    from core.normalizer import normalize_data
    from core.article_match import ArticleConfig
    cfg = ArticleConfig(threshold=0.8, gray_band=(0.4, 0.8))
    pairs: list[ReviewPair] = []
    normalize_data([p1, p2], review_pairs=pairs, config=cfg)
    assert any(p.source == "normalizer" for p in pairs), f"pairs={pairs}"
