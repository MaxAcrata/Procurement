# GUI Threads, OCR Confidence, Match Review & Calibration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three stability features from `docs/compose/specs/2026-10-19-gui-ocr-matching-stability-design.md`: non-blocking GUI work, OCR confidence flags, and a match review queue with threshold calibration CLI.

**Architecture:** One shared `TaskRunner` (QThread worker) wraps all heavy VM→backend calls; OCR mean word-confidence lands on `Product.ocr_confidence`; gray-band article matches feed a JSON-backed review queue and a `calibrate` CLI command.

**Tech Stack:** Python 3.12, PySide6 (QThread/QObject signals), pytesseract `image_to_data`, pytest (no new deps).

## Global Constraints

- Test command: `.venv\Scripts\python.exe -m pytest tests/ -q` from `C:\Users\Фрол\procurement_agent` (Windows/PowerShell). Full suite must stay green after every task.
- No new dependencies. `pytesseract>=0.3.0` is already in `pyproject.toml`.
- Follow existing MVVM patterns: views never call backend; VMs own signals; `BackendService` ABC is the only GUI→core boundary.
- Constants (spec): match `threshold=0.75`, `gray_band=(0.5, 0.75)`, OCR `low_confidence_threshold=70.0`.
- No task cancellation (YAGNI). Re-entrant `TaskRunner.run` while busy is ignored.
- TDD is mandatory: failing test first, watch it fail for the expected reason, then minimal implementation.
- **Commit steps are listed per template but require explicit user approval before running `git commit`.** If the user has not asked for commits, leave steps checked as "code+tests done" and note "commit deferred".
- Spec file for `Covers:` anchors: `docs/compose/specs/2026-10-19-gui-ocr-matching-stability-design.md` (`[S1]`…`[S5]`).

---

## File Structure

| File | Responsibility |
|---|---|
| `gui/services/task_runner.py` (new) | Run callables on a worker thread; deliver results on the GUI thread |
| `gui/viewmodels/file_upload_vm.py`, `orders_vm.py`, `comparison_vm.py`, `email_vm.py` | Wrap heavy backend calls in `TaskRunner` |
| `models/__init__.py` | `Product.ocr_confidence: float \| None`; `ReviewPair` dataclass |
| `config.py` | `OcrConfig`; `ArticleMatchConfig.gray_band` |
| `parsers/image_parser.py` | `image_to_data` + mean confidence |
| `core/normalizer.py` | Preserve `unit`/`ocr_confidence` on rebuild; emit review pairs |
| `core/article_match.py` | `classify(score) -> match/review/no_match` |
| `core/comparator.py` | Emit gray-band review pairs |
| `gui/services/backend_interface.py`, `backend_impl.py` | Review-pair collection + `match_review.json` persistence |
| `gui/views/review_page.py` (new), `gui/viewmodels/review_vm.py` (new) | Review queue UI |
| `gui/main_window.py`, `gui/views/__init__.py` | Register «Ревью пар» nav page |
| `gui/views/parsed_data_page.py` | Highlight low-confidence rows |
| `main.py` | `calibrate` command |
| `tests/test_task_runner.py`, `test_ocr_confidence.py`, `test_match_review.py`, `test_calibrate.py` (new) | Regression suites |

---

### Task 1: TaskRunner helper

**Covers:** [S1]

**Files:**
- Create: `gui/services/task_runner.py`
- Test: `tests/test_task_runner.py`

**Interfaces:**
- Consumes: nothing (standalone).
- Produces: `TaskRunner(parent: QObject | None = None)`, `.busy -> bool`, `.run(fn: Callable[[], T], on_result: Callable[[T], None], on_error: Callable[[str], None]) -> bool` (False if busy). Later tasks (Task 2) depend on these exact names.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_task_runner.py
"""TaskRunner — background execution contract (S1)."""

from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication

from gui.services.task_runner import TaskRunner


def _process_until(predicate, timeout_s: float = 3.0) -> bool:
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_run_executes_fn_off_caller_and_delivers_result():
    runner = TaskRunner()
    seen: list[str] = []
    main_thread_id = None

    def heavy():
        return "done"

    assert runner.run(heavy, on_result=seen.append, on_error=seen.append) is True
    assert runner.busy is True
    assert _process_until(lambda: seen == ["done"])
    assert runner.busy is False


def test_run_delivers_error_message_on_exception():
    runner = TaskRunner()
    errors: list[str] = []

    def boom():
        raise ValueError("kaput")

    assert runner.run(boom, on_result=lambda r: None, on_error=errors.append) is True
    assert _process_until(lambda: bool(errors))
    assert "kaput" in errors[0]


def test_second_run_is_ignored_while_busy():
    runner = TaskRunner()
    results: list[str] = []

    def slow():
        time.sleep(0.2)
        return "first"

    assert runner.run(slow, on_result=results.append, on_error=lambda e: None) is True
    assert runner.run(lambda: "second", on_result=results.append, on_error=lambda e: None) is False
    assert _process_until(lambda: results == ["first"])
    assert results == ["first"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_task_runner.py -q`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'gui.services.task_runner'`

- [ ] **Step 3: Minimal implementation**

```python
# gui/services/task_runner.py
"""Run heavy callables off the GUI thread."""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QMetaObject, QThread, Signal, Slot, Qt

logger = logging.getLogger(__name__)


class _Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as exc:
            logger.exception("Background task failed")
            self.failed.emit(str(exc))


class TaskRunner(QObject):
    """Executes callables on a worker thread; delivers results on the GUI thread."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._thread.start()
        self._busy = False
        self._on_result: Callable[[Any], None] | None = None
        self._on_error: Callable[[str], None] | None = None

    @property
    def busy(self) -> bool:
        return self._busy

    def run(
        self,
        fn: Callable[[], Any],
        on_result: Callable[[Any], None],
        on_error: Callable[[str], None],
    ) -> bool:
        """Start fn on the worker thread. Returns False while another task runs."""
        if self._busy:
            return False
        self._busy = True
        self._on_result = on_result
        self._on_error = on_error

        worker = _Worker(fn)
        worker.moveToThread(self._thread)
        worker.finished.connect(self._deliver_result)
        worker.failed.connect(self._deliver_error)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        QMetaObject.invokeMethod(worker, "run", Qt.ConnectionType.QueuedConnection)
        return True

    @Slot(object)
    def _deliver_result(self, result: Any) -> None:
        self._busy = False
        callback, self._on_result, self._on_error = self._on_result, None, None
        if callback is not None:
            callback(result)

    @Slot(str)
    def _deliver_error(self, message: str) -> None:
        self._busy = False
        callback, self._on_result, self._on_error = self._on_error, None, None
        if callback is not None:
            callback(message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_task_runner.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit** (deferred unless user approved)

```bash
git add gui/services/task_runner.py tests/test_task_runner.py
git commit -m "feat(gui): TaskRunner for background heavy operations"
```

---

### Task 2: Wire all four VMs through TaskRunner

**Covers:** [S1]

**Files:**
- Modify: `gui/viewmodels/file_upload_vm.py` (whole `process_files`), `gui/viewmodels/orders_vm.py` (`generate_orders`), `gui/viewmodels/comparison_vm.py` (`compare`), `gui/viewmodels/email_vm.py` (`send_emails`)
- Test: `tests/test_task_runner.py` (append)

**Interfaces:**
- Consumes: `TaskRunner.run(...)` from Task 1.
- Produces: unchanged VM signal contracts (`processing_started/finished`, `orders_generated`, `comparison_done`, `emails_sent`, `error_occurred`).

- [ ] **Step 1: Write failing tests** (append to `tests/test_task_runner.py`)

```python
from pathlib import Path

from gui.viewmodels.file_upload_vm import FileUploadViewModel


class _FakeBackend:
    def __init__(self, result=None, error=None):
        self._result = result or {"status": "success", "count": 1, "errors": []}
        self._error = error
        self.calls = 0

    def process_files(self, files):
        self.calls += 1
        if self._error:
            raise RuntimeError(self._error)
        return self._result


def test_file_upload_vm_processes_in_background_and_emits_signals():
    backend = _FakeBackend(result={"status": "success", "count": 2, "errors": []})
    vm = FileUploadViewModel(backend)
    started: list[bool] = []
    finished: list[dict] = []
    vm.processing_started.connect(lambda: started.append(True))
    vm.processing_finished.connect(finished.append)

    vm._files = [Path("a.xlsx")]
    vm.process_files()

    assert started == [True]  # synchronous signal before task
    assert _process_until(lambda: bool(finished))
    assert finished[0]["count"] == 2
    assert backend.calls == 1


def test_file_upload_vm_error_goes_to_error_occurred():
    backend = _FakeBackend(error="boom")
    vm = FileUploadViewModel(backend)
    errors: list[str] = []
    vm.error_occurred.connect(errors.append)

    vm._files = [Path("a.xlsx")]
    vm.process_files()

    assert _process_until(lambda: bool(errors))
    assert "boom" in errors[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_task_runner.py -q`
Expected: new tests FAIL — `process_files` still synchronous / error path emits nothing matching ("boom" not in errors after timeout or AttributeError on unused runner).

- [ ] **Step 3: Implement** — same wrapping pattern in each VM.

`file_upload_vm.py` — replace `process_files` and `__init__` tail:

```python
from gui.services.task_runner import TaskRunner


class FileUploadViewModel(QObject):
    ...

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._files: list[Path] = []
        self._runner = TaskRunner(self)

    def process_files(self):
        if not self._files:
            self.error_occurred.emit("No files to process")
            return
        if self._runner.busy:
            return
        files = self._files.copy()
        self.processing_started.emit()
        self._runner.run(
            lambda: self._backend.process_files(files),
            on_result=self.processing_finished.emit,
            on_error=self.error_occurred.emit,
        )
```

`orders_vm.py` — replace `generate_orders`:

```python
def generate_orders(self, output_dir: Path = Path("output")):
    if self._runner.busy:
        return
    self._runner.run(
        lambda: self._backend.generate_orders(output_dir),
        on_result=self._on_orders_generated,
        on_error=self.error_occurred.emit,
    )


def _on_orders_generated(self, files: list):
    self._generated_files = files
    self.orders_generated.emit(self._generated_files)
    self.refresh()
```

(Add `self._runner = TaskRunner(self)` in `__init__` and the `TaskRunner` import.)

`comparison_vm.py` — replace `compare`:

```python
    def compare(self, order_path: Path, invoice_paths: list[Path]):
        if self._runner.busy:
            return
        paths = list(invoice_paths)

        def work():
            results = self._backend.compare(order_path, paths)
            self._results = results
            self._summary = self._calculate_summary()
            return (results, self._summary)

        def done(payload):
            results, summary = payload
            self.comparison_done.emit(results, summary)

        self._runner.run(work, on_result=done, on_error=self.error_occurred.emit)
```

(Add `self._runner = TaskRunner(self)` in `__init__`.)

`email_vm.py` — replace `send_emails`:

```python
def send_emails(self):
    if self._runner.busy:
        return
    self._runner.run(
        self._backend.send_emails,
        on_result=self._on_emails_sent,
        on_error=self.error_occurred.emit,
    )


def _on_emails_sent(self, results: list):
    self.emails_sent.emit(results)
    self.refresh()
```

(Add `self._runner = TaskRunner(self)` in `__init__`. `update_email` stays synchronous — it is a tiny JSON write.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_task_runner.py tests/test_email_sending.py tests/test_p2_ux.py -q`
Expected: all PASS (existing VM/backend contracts intact).

- [ ] **Step 5: Commit** (deferred unless user approved)

```bash
git add gui/viewmodels tests/test_task_runner.py
git commit -m "feat(gui): run heavy VM operations on background threads"
```

---

### Task 3: OCR confidence on Product + image_to_data

**Covers:** [S2]

**Files:**
- Modify: `config.py` (add `OcrConfig`, wire into `AppConfig`), `models/__init__.py` (`Product.ocr_confidence`), `parsers/image_parser.py`, `core/normalizer.py` (preserve fields on rebuild)
- Test: `tests/test_ocr_confidence.py`

**Interfaces:**
- Consumes: `Product` dataclass (extend with defaulted field — constructors stay compatible).
- Produces: `Product.ocr_confidence: float | None`; `settings.ocr.low_confidence_threshold: float = 70.0`; `parse_image` fills confidence on products from OCR and appends a warning to `errors` when mean < threshold. Task 4 consumes `product.ocr_confidence` and `settings.ocr.low_confidence_threshold`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ocr_confidence.py
"""OCR confidence flags (S2)."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from config import settings
from models import Product
from parsers.image_parser import parse_image


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
    _install_fake_ocr(monkeypatch, confs=["95", "80", "40"], texts=["Петля", "71B3750", "Кол-во:10"])
    f = tmp_path / "scan.png"
    f.write_bytes(b"png")

    result = parse_image(f)

    assert result.products, "expected at least one product"
    for p in result.products:
        assert p.ocr_confidence is not None
        assert abs(p.ocr_confidence - (95 + 80 + 40) / 3) < 0.01
    assert not any("низким OCR-confidence" in e for e in result.errors)  # 71.67 >= 70


def test_parse_image_warns_when_mean_below_threshold(monkeypatch, tmp_path):
    _install_fake_ocr(monkeypatch, confs=["40", "30"], texts=["Артикул:ABC123", "Кол-во:5"])  # mean 35
    f = tmp_path / "bad.png"
    f.write_bytes(b"png")

    result = parse_image(f)

    assert any("низким OCR-confidence" in e for e in result.errors)
    assert result.products and result.products[0].ocr_confidence == 35.0


def test_normalize_preserves_unit_and_ocr_confidence():
    from core.normalizer import normalize_data

    p = Product(name="Петля", article="71B3750", quantity=1.0, supplier="Blum", unit="шт", ocr_confidence=42.0)
    out = normalize_data([p])
    assert out and out[0].unit == "шт"
    assert out[0].ocr_confidence == 42.0


def test_ocr_threshold_config_exists():
    assert settings.ocr.low_confidence_threshold == 70.0
```

Note: `parse_image` keeps its existing local-import style; the tests stub `pytesseract`/`PIL.Image` in `sys.modules` so they pass whether or not those packages are installed in the venv. Do NOT add a loader helper to production code.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ocr_confidence.py -q`
Expected: FAIL — `AttributeError`/`TypeError` (no `ocr_confidence`), `settings.ocr` missing, errors list empty (no threshold warning), `unit` dropped by normalizer.

- [ ] **Step 3: Implement**

`config.py` — add after `RetryConfig` and wire into `AppConfig`:

```python
@dataclass(frozen=True)
class OcrConfig:
    low_confidence_threshold: float = 70.0
```

```python
@dataclass(frozen=True)
class AppConfig:
    smtp: SmtpConfig = field(default_factory=SmtpConfig)
    article: ArticleMatchConfig = field(default_factory=ArticleMatchConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    ocr: OcrConfig = field(default_factory=OcrConfig)
    emails_db_path: Path = EMAILS_DB_PATH
    output_dir: Path = OUTPUT_DIR
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
```

`models/__init__.py` — `Product` becomes:

```python
@dataclass
class Product:
    name: str
    article: str
    quantity: float
    supplier: str = "UNKNOWN"
    unit: str = ""
    ocr_confidence: float | None = None
```

`parsers/image_parser.py` — replace the OCR block inside `parse_image`:

```python
    confidences: list[float] = []
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(str(file_path))
        data = pytesseract.image_to_data(img, lang="rus+eng", output_type=pytesseract.Output.DICT)
        words: list[str] = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            try:
                c = float(conf)
            except (TypeError, ValueError):
                continue
            if text and text.strip() and c >= 0:
                words.append(text)
                confidences.append(c)
        raw_text = " ".join(words)
    except ImportError:
        errors.append("pytesseract not installed, trying manual extraction")
    except Exception as e:
        logger.exception("OCR error for %s", file_path)
        errors.append(f"OCR error: {e}")
```

after `products = extract_products_from_text(raw_text)` add:

```python
mean_conf = sum(confidences) / len(confidences) if confidences else None
if mean_conf is not None:
    for p in products:
        p.ocr_confidence = mean_conf
    if mean_conf < settings.ocr.low_confidence_threshold:
        errors.append(
            f"Низкий OCR-confidence: среднее {mean_conf:.1f} < порога {settings.ocr.low_confidence_threshold}"
        )
```

(Import `settings` from `config` at module top.)

`core/normalizer.py` — the rebuild in `normalize_data` preserves both fields (also fixes the lost-`unit` bug):

```python
        product = Product(
            name=_normalize_name(p.name),
            article=_normalize_article(p.article),
            quantity=p.quantity,
            supplier=_normalize_supplier(p.supplier),
            unit=p.unit,
            ocr_confidence=p.ocr_confidence,
        )
```

Also preserve on the merge in `_merge_duplicates`:

```python
merged_product = Product(
    name=match_group[0].name,
    article=match_group[0].article,
    quantity=sum(p.quantity for p in match_group),
    supplier=supplier
    if supplier != "UNKNOWN"
    else (next((p.supplier for p in match_group if p.supplier != "UNKNOWN"), "UNKNOWN")),
    unit=next((p.unit for p in match_group if p.unit), ""),
    ocr_confidence=min(
        (p.ocr_confidence for p in match_group if p.ocr_confidence is not None),
        default=None,
    ),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ocr_confidence.py tests/test_normalizer.py tests/test_generators.py -q`
Expected: all PASS (`test_normalizer` must stay green — field carry is additive).

- [ ] **Step 5: Commit** (deferred unless user approved)

```bash
git add config.py models/__init__.py parsers/image_parser.py core/normalizer.py tests/test_ocr_confidence.py
git commit -m "feat(ocr): per-document confidence from image_to_data + low-confidence warning"
```

---

### Task 4: Highlight low-confidence rows in «Данные»

**Covers:** [S2]

**Files:**
- Modify: `gui/views/parsed_data_page.py` (`_filter_data`)
- Test: `tests/test_ocr_confidence.py` (append; Qt widget test)

**Interfaces:**
- Consumes: `Product.ocr_confidence`, `settings.ocr.low_confidence_threshold` (Task 3).
- Produces: visual-only; no new API.

- [ ] **Step 1: Write failing test** (append)

```python
def test_parsed_data_page_highlights_low_confidence_rows(qapp):
    # reuse the qapp fixture idiom from tests/test_p2_ux.py (QApplication.instance() or QApplication([]))
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.parsed_data_vm import ParsedDataViewModel
    from gui.views.parsed_data_page import ParsedDataPage
    from PySide6.QtGui import QColor

    backend = ProcurementBackend()
    backend._products = [
        Product(name="Good", article="ABC-1", quantity=1.0, supplier="S", ocr_confidence=95.0),
        Product(name="Bad", article="ABC-2", quantity=1.0, supplier="S", ocr_confidence=30.0),
    ]
    vm = ParsedDataViewModel(backend)
    page = ParsedDataPage(vm)
    page._filter_data()

    assert page.table.rowCount() == 2
    good_bg = page.table.item(0, 0).background().color().name()
    bad_bg = page.table.item(1, 0).background().color().name()
    assert bad_bg != good_bg
    assert QColor(bad_bg) != QColor()  # highlighted row has explicit background
```

(If the Qt widget test proves brittle, a lighter acceptable test asserts a pure helper `is_low_confidence(product) -> bool` and that `_filter_data` calls it — but prefer the widget assertion above.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ocr_confidence.py::test_parsed_data_page_highlights_low_confidence_rows -q`
Expected: FAIL — both rows share the default background (no highlight code yet).

- [ ] **Step 3: Implement** — end of `_filter_data` in `parsed_data_page.py`:

```python
self.table.load_data([[p.supplier, p.name, p.article, str(p.quantity)] for p in filtered])
for row_idx, p in enumerate(filtered):
    if p.ocr_confidence is not None and p.ocr_confidence < settings.ocr.low_confidence_threshold:
        brush = QBrush(QColor("#fab387"))  # existing warning idiom from DataTable status colors
        for col in range(4):
            item = self.table.item(row_idx, col)
            if item is not None:
                item.setBackground(brush)
```

Imports to add: `from PySide6.QtGui import QBrush, QColor` and `from config import settings`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ocr_confidence.py -q`
Expected: PASS.

- [ ] **Step 5: Commit** (deferred unless user approved)

```bash
git add gui/views/parsed_data_page.py tests/test_ocr_confidence.py
git commit -m "feat(gui): highlight low OCR-confidence rows in parsed data table"
```

---

### Task 5: `classify()` + gray-band review-pair collection

**Covers:** [S3]

**Files:**
- Modify: `core/article_match.py` (`classify`), `config.py` (`ArticleMatchConfig.gray_band`), `models/__init__.py` (`ReviewPair`), `core/comparator.py`, `core/normalizer.py`
- Test: `tests/test_match_review.py`

**Interfaces:**
- Consumes: `calculate_score` (existing).
- Produces: `classify(score: float, config: ArticleConfig | None = None) -> str` returning `"match" | "review" | "no_match"`; `ReviewPair(article_a: str, article_b: str, score: float, source: str)` (frozen dataclass); `compare_tables(..., review_pairs: list[ReviewPair] | None = None)` and `normalize_data(products, review_pairs: list[ReviewPair] | None = None)` append gray-band pairs when the list is provided. Task 6 persists/decides these pairs.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_match_review.py
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
    assert classify(score) == "review"  # guard: fixture pair is inside the band

    pairs: list[ReviewPair] = []
    compare_tables(order, invoice, review_pairs=pairs)

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
    pairs: list[ReviewPair] = []
    normalize_data(products, review_pairs=pairs)
    assert any(p.source == "normalizer" for p in pairs)


def test_review_pairs_optional_and_backward_compatible():
    # Existing call shape (no review_pairs) must keep working.
    out = compare_tables(
        [Product(name="A", article="ABC-1", quantity=1.0)],
        [Product(name="A", article="ABC-1", quantity=1.0)],
    )
    assert len(out) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_match_review.py -q`
Expected: FAIL — `ImportError: cannot import name 'classify'/'ReviewPair'`, `TypeError: unexpected keyword 'review_pairs'`. (If the first guard `classify(score) == "review"` fails, adjust the fixture articles so their score lands in [0.5, 0.75) — the known example `RT110GR.1/000/600` vs `RT110GR.1/128/150` scores ≈ 0.464 per README; in that case use `ArticleConfig(threshold=0.8, gray_band=(0.4, 0.8))` for the collection tests and assert with that config explicitly passed through.)

- [ ] **Step 3: Implement**

`models/__init__.py` — add and export:

```python
@dataclass(frozen=True)
class ReviewPair:
    article_a: str
    article_b: str
    score: float
    source: str
```

`core/article_match.py` — extend `ArticleConfig` and add `classify`:

```python
@dataclass(frozen=True)
class ArticleConfig:
    prefix_length: int = 8
    threshold: float = 0.75
    gray_band: tuple[float, float] = (0.5, 0.75)
    weight_prefix: float = 0.4
    weight_main_token: float = 0.3
    weight_numeric: float = 0.2
    weight_fuzzy: float = 0.1
```

```python
def classify(score: float, config: ArticleConfig | None = None) -> str:
    """Classify a match score as 'match' | 'review' | 'no_match'."""
    cfg = config or _default_config
    if score >= cfg.threshold:
        return "match"
    if score >= cfg.gray_band[0]:
        return "review"
    return "no_match"
```

`core/comparator.py` — extend `compare_tables` signature and collect inside the candidate loop:

```python
def compare_tables(
    order_products: list[Product],
    invoice_products: list[Product],
    config: ArticleConfig | None = None,
    review_pairs: list[ReviewPair] | None = None,
) -> list[ComparisonItem]:
```

In the double loop after `score = calculate_score(...)`:

```python
if score >= threshold:
    candidates.append((score, oi, ii))
elif review_pairs is not None and classify(score, config) == "review":
    review_pairs.append(
        ReviewPair(
            article_a=order_item.article,
            article_b=inv_item.article,
            score=score,
            source="comparator",
        )
    )
```

(Import `classify` and `ReviewPair`.)

`core/normalizer.py` — extend `normalize_data` and `_merge_duplicates`:

```python
def normalize_data(
    products: list[Product],
    review_pairs: list[ReviewPair] | None = None,
) -> list[Product]:
```

pass `review_pairs` through to `_merge_duplicates(cleaned, review_pairs=review_pairs)`; in the pairwise loop replace the bare `compare_articles` call with:

```python
score = calculate_score(p1.article, p2.article, config)
if score >= (config or ArticleConfig()).threshold:
    match_group.append(p2)
    used.add(j)
elif review_pairs is not None and classify(score, config) == "review":
    review_pairs.append(
        ReviewPair(
            article_a=p1.article,
            article_b=p2.article,
            score=score,
            source="normalizer",
        )
    )
```

(Import `calculate_score`, `classify`, `ReviewPair` alongside the existing `compare_articles` import; keep `compare_articles` exported for tests.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_match_review.py tests/test_article_match.py tests/test_comparator.py tests/test_normalizer.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit** (deferred unless user approved)

```bash
git add core models config.py tests/test_match_review.py
git commit -m "feat(match): classify() with gray band and review-pair collection"
```

---

### Task 6: Review queue backend + GUI page

**Covers:** [S3]

**Files:**
- Modify: `gui/services/backend_interface.py`, `gui/services/backend_impl.py`, `gui/main_window.py`, `gui/views/__init__.py`, `procurement.spec` (hiddenimports — add new modules)
- Create: `gui/viewmodels/review_vm.py`, `gui/views/review_page.py`
- Test: `tests/test_match_review.py` (append)

**Interfaces:**
- Consumes: `ReviewPair` (Task 5), `ProcurementBackend._pending_review_pairs` filled via `process_files`/`compare` (wire `review_pairs=[]` at call sites in `backend_impl.py`: `self._pending_review_pairs = []` then pass it into `normalize_data`/`compare_tables`).
- Produces: `BackendService.get_review_pairs() -> list[dict]` (keys: `article_a`, `article_b`, `score`, `source`); `BackendService.decide_review_pair(article_a: str, article_b: str, decision: str) -> None` with `decision in {"confirmed", "rejected"}`; persistence file `match_review.json` beside `emails_db.json`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_match_review.py`)

```python
def test_backend_review_queue_persist_and_decide(tmp_path, monkeypatch):
    from gui.services.backend_impl import ProcurementBackend
    import gui.services.backend_impl as bi

    monkeypatch.setattr(bi.settings, "emails_db_path", tmp_path / "emails_db.json")
    # match_review path must derive from the same settings root:
    monkeypatch.setattr("config.settings.emails_db_path", tmp_path / "emails_db.json", raising=False)

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
```

(Implementation note: derive the JSON path as `settings.emails_db_path.parent / "match_review.json"` so the monkeypatch above works and no new config key is needed.)

```python
def test_review_vm_emits_and_refreshes(qapp):
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.review_vm import ReviewViewModel

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_match_review.py -q`
Expected: FAIL — `AttributeError: 'ProcurementBackend' object has no attribute 'get_review_pairs'`, import error for `review_vm`.

- [ ] **Step 3: Implement**

`gui/services/backend_interface.py` — add abstract methods:

```python
@abstractmethod
def get_review_pairs(self) -> list[dict]:
    """Return pending gray-band article pairs awaiting review."""
    ...


@abstractmethod
def decide_review_pair(self, article_a: str, article_b: str, decision: str) -> None:
    """Record a review decision ('confirmed' | 'rejected') and persist it."""
    ...
```

`gui/services/backend_impl.py`:

```python
    def __init__(self) -> None:
        ...
        self._pending_review_pairs: list[ReviewPair] = []
        self._review_decisions: list[dict] = []
        self._load_review_db()
        self._load_emails_db()
```

```python
def _review_db_path(self) -> Path:
    return settings.emails_db_path.parent / "match_review.json"


def _load_review_db(self) -> None:
    path = self._review_db_path()
    if path.exists():
        try:
            self._review_decisions = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load match review DB from %s", path)
            self._review_decisions = []


def _save_review_db(self) -> None:
    try:
        self._review_db_path().write_text(
            json.dumps(self._review_decisions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to save match review DB")


def get_review_pairs(self) -> list[dict]:
    decided = {(d["article_a"], d["article_b"]) for d in self._review_decisions}
    return [
        {"article_a": p.article_a, "article_b": p.article_b, "score": p.score, "source": p.source}
        for p in self._pending_review_pairs
        if (p.article_a, p.article_b) not in decided
    ]


def decide_review_pair(self, article_a: str, article_b: str, decision: str) -> None:
    if decision not in ("confirmed", "rejected"):
        raise ValueError(f"Invalid decision: {decision}")
    self._review_decisions.append(
        {
            "article_a": article_a,
            "article_b": article_b,
            "decision": decision,
            "ts": datetime.now().isoformat(),
        }
    )
    self._save_review_db()
```

Wire collection: in `process_files` and `compare`, replace `normalize_data(...)` / `compare_tables(...)` calls to pass `review_pairs=self._pending_review_pairs` (reset the list at the start of each of those methods).

`gui/viewmodels/review_vm.py` (new):

```python
"""Review-queue ViewModel for gray-band article pairs."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gui.services.backend_interface import BackendService


class ReviewViewModel(QObject):
    data_changed = Signal()
    error_occurred = Signal(str)

    def __init__(self, backend: BackendService, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._pairs: list[dict] = []

    @property
    def pairs(self) -> list[dict]:
        return self._pairs.copy()

    def refresh(self):
        self._pairs = self._backend.get_review_pairs()
        self.data_changed.emit()

    def decide(self, article_a: str, article_b: str, decision: str):
        try:
            self._backend.decide_review_pair(article_a, article_b, decision)
            self.refresh()
        except Exception as e:
            self.error_occurred.emit(str(e))
```

`gui/views/review_page.py` (new) — follow `suppliers_page.py` layout idiom: title, `DataTable`, per-row «Подтвердить» / «Отклонить» buttons (or two buttons acting on `currentRow`), `status_label` for `error_occurred`. Columns: Артикул A, Артикул B, Score, Источник. Buttons call `self.vm.decide(a, b, "confirmed"/"rejected")` using the selected row's pair.

`gui/views/__init__.py` — export `ReviewPage`. `gui/main_window.py` — add `("review", "Ревью пар", ReviewPage)` to `NAV_ITEMS` (after «Поставщики»), instantiate `ReviewViewModel` in `_setup_viewmodels`, add to `page_map`, `vm_review.refresh()` on navigate. `procurement.spec` — add `gui.views.review_page` and `gui.viewmodels.review_vm` to `hiddenimports`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_match_review.py -q`
Expected: PASS. Then full suite: `.venv\Scripts\python.exe -m pytest tests/ -q` — all green.

- [ ] **Step 5: Commit** (deferred unless user approved)

```bash
git add gui tests/test_match_review.py procurement.spec
git commit -m "feat(match): review queue backend, GUI page, match_review.json persistence"
```

---

### Task 7: `calibrate` CLI command

**Covers:** [S3]

**Files:**
- Modify: `main.py` (new `calibrate` command)
- Test: `tests/test_calibrate.py`

**Interfaces:**
- Consumes: `calculate_score`, `ArticleConfig` (Task 5), `match_review.json` schema `{article_a, article_b, score?, decision}` from Task 6.
- Produces: `calibrate(labels: Path, apply: bool) -> None` typer command: prints precision/recall/F1 table for thresholds 0.50–0.95 step 0.05; recommends max-F1 threshold (ties → higher precision); `--apply` rewrites the `threshold` value inside `ArticleMatchConfig` in `config.py` text.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_calibrate.py
"""Threshold calibration over labeled review pairs (S3)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

import main as main_mod


def _write_labels(path, pairs):
    path.write_text(json.dumps(pairs), encoding="utf-8")


def test_calibrate_prints_table_and_recommended_threshold(tmp_path):
    labels = tmp_path / "match_review.json"
    # Confirmed pairs should score high; rejected low (use real calculate_score values).
    from core.article_match import calculate_score

    hi_a, hi_b = "71B3750", "71B3750"
    lo_a, lo_b = "RT110GR.1/000/600", "RT110GR.1/128/150"
    assert calculate_score(hi_a, hi_b) >= 0.9
    assert calculate_score(lo_a, lo_b) <= 0.5
    _write_labels(
        labels,
        [
            {"article_a": hi_a, "article_b": hi_b, "decision": "confirmed"},
            {"article_a": lo_a, "article_b": lo_b, "decision": "rejected"},
            {"article_a": "71B3751", "article_b": "71B3751", "decision": "confirmed"},
        ],
    )

    result = CliRunner().invoke(main_mod.app, ["calibrate", "--labels", str(labels)])
    assert result.exit_code == 0, result.output
    assert "precision" in result.output.lower()
    assert "recommended" in result.output.lower()


def test_calibrate_apply_rewrites_config_threshold(tmp_path):
    import config as config_mod

    labels = tmp_path / "match_review.json"
    _write_labels(
        labels,
        [
            {"article_a": "71B3750", "article_b": "71B3750", "decision": "confirmed"},
            {"article_a": "XYZ-1", "article_b": "XYZ-9", "decision": "rejected"},
        ],
    )
    cfg_src = tmp_path / "config.py"
    cfg_src.write_text(
        "class ArticleMatchConfig:\n    threshold: float = 0.75\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main_mod.app,
        ["calibrate", "--labels", str(labels), "--apply", "--config", str(cfg_src)],
    )
    assert result.exit_code == 0, result.output
    text = cfg_src.read_text(encoding="utf-8")
    assert "threshold" in text and "0.75" not in text
```

(If you prefer not to add `--config`, run `--apply` against a copy of `config.py` via an explicit `--config` option as above — the option is required for testability; default is the real `config.py` path.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrate.py -q`
Expected: FAIL — `No such command 'calibrate'`.

- [ ] **Step 3: Implement** — in `main.py`:

```python
@app.command()
def calibrate(
    labels: Path = typer.Option("match_review.json", "--labels", help="Path to labeled pairs JSON"),
    config_path: Path | None = typer.Option(None, "--config", help="config.py to rewrite with --apply"),
    apply: bool = typer.Option(False, "--apply", help="Write best threshold into config.py"),
) -> None:
    """Sweep match thresholds over labeled review pairs; print P/R/F1 and recommend one."""
    from core.article_match import calculate_score

    if not labels.exists():
        console.print(f"[red]Labels file not found: {labels}[/]")
        raise typer.Exit(1)

    entries = json.loads(labels.read_text(encoding="utf-8"))
    rows = []
    for e in entries:
        score = calculate_score(e["article_a"], e["article_b"])
        rows.append((score, e.get("decision") == "confirmed"))

    if not rows:
        console.print("[yellow]No labeled pairs found.[/]")
        raise typer.Exit(1)

    table = Table("threshold", "precision", "recall", "f1")
    best = None  # (f1, precision, threshold)
    thresholds = [round(0.05 * i + 0.50, 2) for i in range(10)]  # 0.50 .. 0.95
    for t in thresholds:
        tp = sum(1 for s, y in rows if y and s >= t)
        fp = sum(1 for s, y in rows if not y and s >= t)
        fn = sum(1 for s, y in rows if y and s < t)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        table.add_row(f"{t:.2f}", f"{precision:.3f}", f"{recall:.3f}", f"{f1:.3f}")
        if (
            best is None or (f1, precision, t) > best[0:1] + best[1:2] + best[2:3]
            if False
            else (f1 > best[0] or (f1 == best[0] and precision > best[1]))
        ):
            best = (f1, precision, t)
    console.print(table)
    if best is None:
        raise typer.Exit(1)
    f1, precision, t = best
    console.print(f"[bold green]Recommended threshold: {t:.2f}[/] (F1={f1:.3f}, precision={precision:.3f})")

    if apply:
        target = config_path or (Path(__file__).parent / "config.py")
        text = target.read_text(encoding="utf-8")
        new_text, n = re.subn(
            r"(threshold:\s*float\s*=\s*)[0-9.]+",
            rf"\g<1>{t}",
            text,
            count=1,
        )
        if n != 1:
            console.print("[red]Could not locate threshold field in config.py[/]")
            raise typer.Exit(1)
        target.write_text(new_text, encoding="utf-8")
        console.print(f"[green]Wrote threshold={t} to {target}[/]")
```

Clean up the `best` update line to the readable form:

```python
        candidate = (f1, precision, t)
        if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] > best[1]):
            best = candidate
```

(Add `import re` at top of `main.py` if absent; `Table` is already imported from `rich.table` in the existing summary helpers — verify and reuse.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_calibrate.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + mypy**

Run: `.venv\Scripts\python.exe -m pytest tests/ -q` then `.venv\Scripts\python.exe -m mypy --ignore-missing-imports core/ models/ config.py parsers/ generators/ mailer/`
Expected: all tests PASS; mypy `Success: no issues found` (CI gate must stay enabled).

- [ ] **Step 6: Commit** (deferred unless user approved)

```bash
git add main.py tests/test_calibrate.py
git commit -m "feat(match): calibrate CLI sweeps thresholds over labeled pairs"
```

---

## Self-Review record

1. **Spec coverage:** S1 → Tasks 1–2; S2 → Tasks 3–4; S3 → Tasks 5–7; S4 (out of scope) intentionally uncovered; S5 risks addressed in constraints (busy-flag, fixture-pinned OCR output, pair dedupe). No `Covers:` ID outside S1–S5.
2. **Placeholder scan:** no TBD/TODO; every code step has concrete code. Task 6 review-page body references `suppliers_page.py` idiom for layout — acceptable pattern pointer with explicit columns/buttons spelled out.
3. **Type consistency:** `TaskRunner.run(fn, on_result, on_error) -> bool` (T1 ↔ T2); `ReviewPair(article_a, article_b, score, source)` (T5 ↔ T6); `get_review_pairs()/decide_review_pair()` (T6 ↔ T6 tests); `classify(score, config) -> str` (T5 ↔ T5 tests); `Product.ocr_confidence` (T3 ↔ T4).

