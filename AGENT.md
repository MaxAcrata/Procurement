# AGENT.md — Procurement Agent

Практическое руководство для агентов, работающих с кодовой базой.

## Обзор

Desktop-приложение (Windows) для автоматизации закупок: парсинг документов → нормализация → группировка → Excel-заявки → сравнение → email. Два режима: GUI (PySide6 MVVM) и CLI (Typer).

- **Python 3.12**, зависимости через `uv sync`
- **Тесты:** `& .venv\Scripts\python.exe -m pytest tests/ -q` (153 tests)
- **Типы:** `mypy --ignore-missing-imports core/ models/ config.py parsers/ generators/ mailer/`
- **Точка входа:** `gui_app.py` (GUI), `main.py` (CLI)

## Архитектурные принципы

### MVVM (GUI)

```
View (gui/views/) → ViewModel (gui/viewmodels/) → BackendService (ABC) → core/ + parsers/
```

- Views **никогда** не вызывают backend напрямую — только через ViewModel-сигналы.
- ViewModel-ы владеют `TaskRunner` для тяжёлых операций (парсинг, генерация, сравнение, email).
- `BackendService` (`gui/services/backend_interface.py`) — единственный контракт GUI→core.
- `ProcurementBackend` (`gui/services/backend_impl.py`) — единственная реализация.

### TaskRunner (фоновые потоки)

`gui/services/task_runner.py` — обёртка над `QThread` + `QObject` worker.

```python
runner = TaskRunner(parent)
runner.run(fn, on_result=callback, on_error=callback)  # -> bool (False if busy)
```

- Пока задача выполняется, повторный `run()` игнорируется (busy-flag).
- Нет отмены (YAGNI для single-user desktop).
- **Важно:** `TaskRunner.shutdown()` вызывается в `__del__`. Не удаляйте его — без этого QThread виснет при GC.
- Worker **не трогает GUI-объекты** — только чистые callable'ы.

### Данные

- `models.Product` — `name, article, quantity, supplier, unit, ocr_confidence`.
- `models.ReviewPair` (frozen) — `article_a, article_b, score, source` — gray-band пары.
- Нормализация **сохраняет** `unit` и `ocr_confidence` (не теряйте поля при rebuild).

## Ключевые паттерны

### TDD обязателен для фиксов

1. Пиши падающий тест → убедись, что падает по нужной причине.
2. Минимальная реализация → тест зелёный.
3. Полный набор зелёный.

### OCR confidence (S2)

- `parse_image` использует `pytesseract.image_to_data` (НЕ `image_to_string`).
- `ocr_confidence` = средний word conf (0–100). `None` = не OCR-источник.
- Порог: `settings.ocr.low_confidence_threshold = 70`.
- Строки ниже порога подсвечиваются в `parsed_data_page` (`#fab387`).

### Match classify + review queue (S3)

```python
classify(score, config) -> "match" | "review" | "no_match"
# match: score >= threshold (0.75)
# review: gray_band[0] <= score < threshold (0.5–0.75)
# no_match: score < gray_band[0]
```

- `compare_tables()` и `normalize_data()` принимают `review_pairs: list[ReviewPair] | None`.
- Backend собирает пары в `self._pending_review_pairs`, решения пишутся в `match_review.json`.
- CLI `calibrate` — sweep 0.50–0.95 step 0.05, рекомендует max-F1. `--apply` пишет в `config.py`.

### Excel-генерация

- `openpyxl`. Стили: `PatternFill`, `Font(bold=True)`, `Border(Side(...))`, `Alignment(wrap_text=True)`.
- Auto-width: `sum(1.8 if ord(c) > 127 else 1.0 for c in val_str)` (Cyrillic-aware).
- Freeze: `freeze_panes = "A2"`.

### Email

- `mailer/sender.py` — `send_purchase_order_email(to, supplier_name, attachment_path)`.
- Retry: exponential backoff (`RetryConfig.backoff_factor * 2**(attempt-1)`).
- `smtplib.SMTP.starttls()` **не принимает `timeout=`** — timeout только в конструкторе `SMTP(host, port, timeout=)`.
- `is_valid_email()` обязателен в `send_email`/`update_email`.
- Имя вложения санитизируется (`_sanitize_filename`) — Windows запрещает `"`/CR/LF в именах.

## Ловушки

| Проблема | Решение |
|----------|---------|
| QThread виснет при GC | `TaskRunner.__del__` → `shutdown()`; в тестах — fixture с `yield` + `shutdown()` |
| `QMetaObject.invokeMethod(QueuedConnection)` не вызывает слот | Использовать signal-based dispatch (`_Worker._job.emit(fn)`) |
| `AppConfig` frozen — monkeypatch падает | `object.__setattr__(settings, "field", value)` |
| `pytesseract>=5.0.0` неразрешим | Пакет на PyPI максимум 0.3.13; 5.x — это Tesseract ENGINE. Нужен `>=0.3.0` |
| `email/` package shadow stdlib | Называть `mailer/` (не `email/`) |
| `import email.message` падает | Из-за локального `email/` — см. выше |
| `date +%Y-%m-%d` в Bash | PowerShell: `Get-Date -Format yyyy-MM-dd` |
| mypy `no-redef` на ImportError-fallback | `# type: ignore[no-redef]` даже при rename (`ratio as fuzzy_ratio`) |
| Python class definition break | Standalone `def` между методами класса ломает класс — только в конец файла |
| `procurement.spec` hiddenimports | Любой add/delete GUI-модуля требует правки spec |
| reportlab: эмодзи/Unicode → чёрные квадраты | ASCII-альтернативы или `<sub>`/`<super>` в Paragraph |
| Регулярка `extract_products_from_text` | Требует `имя артикул:XXX кол-во:N` — имя обязательно перед ключевым словом |

## Структура тестов

| Файл | Покрывает |
|------|-----------|
| `test_task_runner.py` | TaskRunner + VM integration (фоновые потоки) |
| `test_ocr_confidence.py` | OCR confidence + highlight + config |
| `test_match_review.py` | classify, review pairs, backend queue, ReviewViewModel |
| `test_calibrate.py` | CLI calibrate + --apply |
| `test_article_match.py` | Scoring system |
| `test_comparator.py` | Заявка vs счет |
| `test_normalizer.py` | Нормализация, дедупликация |
| `test_email_sending.py` | P0 email-фиксы |
| `test_p1_email_retry.py` | Retry backoff + validation |
| `test_parsers_stability.py` | Парсеры, PDF fallback, row-drop warnings |
| `test_p2_*.py` | MIME, comparator, UX, hygiene, CI gate |

## Конвенции

- **Язык:** коммиты и код — English; UI-строки — Russian; README — Russian.
- **Типизация:** mypy strict на `core/ models/ config.py parsers/ generators/ mailer/`. GUI — без mypy gate.
- **Линтинг:** `ruff check .` + `ruff format .`. Форматер — `black`-совместимый.
- **CI:** GitHub Actions (`ci.yml`) — ruff → pytest → mypy (gate ON) → build.
- **Коммиты:** не делать без явного запроса пользователя.
- **Ветки:** `main`. Внешний remote: `https://github.com/MaxAcrata/Procurement`.

## Переменные и конфиг

- `config.py` — единственный источник конфигурации (`settings` singleton).
- `settings.ocr.low_confidence_threshold: float = 70`
- `settings.article.threshold: float = 0.75`, `gray_band: (0.5, 0.75)`
- `settings.retry.max_retries = 3`, `backoff_factor = 0.5`, `timeout_seconds = 30`
- `.env` (не коммитить): `SMTP_HOST/PORT/USER/PASSWORD`, `LOG_LEVEL`.
