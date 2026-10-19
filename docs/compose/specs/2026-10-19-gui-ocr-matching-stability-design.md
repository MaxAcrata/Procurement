# Design: GUI background threads, OCR confidence flags, match review queue + calibration

> 2026-10-19 · procurement_agent v0.3 · status: approved in brainstorm (S1–S3) · approach A

## [S1] Background threads for heavy GUI operations

**Problem.** All heavy backend work (PDF/OCR parse, Excel generation, comparison, email send) runs synchronously on the GUI thread (`file_upload_vm.process_files` and sibling VMs call `self._backend.*` inline). The window freezes and the indeterminate progress bar cannot animate.

**Solution.** One shared helper `gui/services/task_runner.py`:

- `TaskRunner(QObject)` owns a `QThread` and dispatches callables via a `Worker(QObject)` moved to that thread (`moveToThread` pattern).
- API: `run(fn: Callable[[], T], on_result: Callable[[T], None], on_error: Callable[[str], None]) -> None`.
- Signals: `worker.finished(result)`, `worker.failed(message)` — connected to the VM callbacks on the GUI thread.
- While a task is in flight: a second `run` is ignored (busy flag). **No cancellation** (YAGNI for single-user desktop).
- Errors from `fn` propagate to `on_error`, which feeds existing `error_occurred` signals.

**Integration.** Each VM's heavy method wraps its backend call in `TaskRunner.run` and keeps its existing signal contract (`processing_started` / `processing_finished`, `orders_generated`, `comparison_ready`, `emails_sent`). Buttons disabled while busy.

**Testing.** Unit tests on `TaskRunner` (invoke `fn`, capture `on_result`/`on_error`; exception path). VM contract tests keep using monkeypatched backend; busy-flag test for ignored re-entry.

## [S2] OCR confidence flags

**Problem.** Image OCR (`parsers/image_parser.py`) uses `image_to_string` and discards per-word confidence. Bad scans silently produce wrong products; `parse_quantity` warnings do not say *why* text was wrong.

**Solution.**

- `models.Product` gains `ocr_confidence: float | None = None` (`None` = not an OCR source).
- `image_parser.parse_image` switches to `pytesseract.image_to_data(..., lang="rus+eng")`:
  - Reconstruct text from word rows (`conf >= 0`, level 5).
  - `ocr_confidence` = mean word confidence (0–100 scale as Tesseract reports).
- Config: `settings.ocr.low_confidence_threshold: float = 70` (new `OcrConfig`).
- When the document mean is below the threshold: append a warning to `DocumentParseResult.errors` ("N позиций с низким OCR-confidence (среднее X < порога Y)") and set `ocr_confidence` on extracted products.
- GUI `parsed_data_page`: highlight rows whose `ocr_confidence` is set and below threshold (existing row-color idiom) — no new column required.
- Other parsers leave the field `None`.

**Testing.** Fixture mocking `image_to_data` output (known conf values) → assert mean, threshold warning presence/absence, field propagation; `image_to_string` no longer used (assert via call recording).

## [S3] Match review queue + threshold calibration

**Problem.** Article matching uses a single hand-picked threshold (0.75) with hand-picked weights. Per benchmark evidence: thresholds do not transfer across data; production systems use a review band and calibrate on labeled pairs.

**Solution.**

- `config.ArticleMatchConfig` gains `gray_band: tuple[float, float] = (0.5, 0.75)`; existing `threshold` remains the MATCH cutoff (0.75).
- `core/article_match.classify(score, config) -> Literal["match","review","no_match"]`:
  - `score >= threshold` → `match`; `score >= gray_band[0]` → `review`; else `no_match`.
- **Pair collection.** When `comparator` (order vs invoice) and `normalizer` (dedup) evaluate pairs whose `classify` is `review`, the GUI backend stores them in `self._pending_review_pairs` (deduped by `(article_a, article_b)`); CLI `process` prints them as a report section.
- **GUI page «Ревью пар»** (registered in `MainWindow.NAV_ITEMS` like SuppliersPage): table of pending pairs with score, buttons «Подтвердить» / «Отклонить»; decisions persisted to `match_review.json` next to `emails_db.json` (`{article_a, article_b, score, decision, ts}`). Confirmed/ rejected pairs leave the pending list.
- **CLI `python main.py calibrate [--labels match_review.json]`**:
  - Loads decided pairs (decision → match/no-match label).
  - Recomputes `calculate_score(article_a, article_b)` for every labeled pair and sweeps thresholds 0.50–0.95 step 0.05: prints precision / recall / F1 table; recommends threshold with max F1 (ties → higher precision).
  - `--apply` rewrites `ArticleMatchConfig.threshold` only in `config.py` if explicitly requested; default is print-only.

**Testing.** `classify` band edges; review-pair registration from comparator/normalizer; `calibrate` on synthetic labels (known F1 peak); persistence round-trip of `match_review.json`.

## [S4] Out of scope

- Task cancellation / queueing multiple concurrent jobs.
- OCR: PaddleOCR / LLM fallbacks, confidence per column/field.
- Matching: learned weights, blocking predicates, embeddings (evidence suggests diminishing returns at document scale).
- Auto-apply of calibrated threshold without `--apply`.

## [S5] Risks

- `QThread` + frozen dataclass backend: worker must not touch GUI objects; only pure callables — enforced by API shape.
- `image_to_data` output shape differs across pytesseract versions — fixture pins the expected DataFrame columns.
- Review queue growth: pending pairs are unique by `(article_a, article_b)`; duplicates collapse.
