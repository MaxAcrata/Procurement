# Procurement Agent

Автоматизация закупочного процесса: парсинг документов, группировка по поставщикам, генерация заявок, сравнение со счетами, отправка email.

## Возможности

- Парсинг PDF, XLSX, DOCX, изображений (OCR через Tesseract)
- Автоопределение столбцов и нормализация данных
- Многоуровневое сравнение артикулов с scoring-системой и gray-band ревью
- Генерация Excel-заявок по поставщикам
- Сравнение заявки со счетами (артикул + количество)
- Отправка email с retry/backoff
- GUI (PySide6, тёмная тема) + CLI (Typer)
- Калибровка порога матчинга по размеченным парам

## Архитектура

```
procurement_agent/
├── config.py                 # Конфиг: SMTP, matching, retry, OCR
├── models/                   # Product, ComparisonItem, ReviewPair, ...
├── core/
│   ├── article_match.py      # Scoring + classify() (match/review/no_match)
│   ├── normalizer.py         # Нормализация, дедупликация, сбор review-pairs
│   ├── comparator.py         # Заявка vs счет
│   └── grouper.py            # Группировка по поставщикам
├── parsers/                  # PDF, XLSX, DOCX, image (OCR + confidence)
├── generators/excel_gen.py   # Генерация Excel
├── mailer/sender.py          # SMTP + retry + MIME
├── gui/
│   ├── main_window.py        # Навигация, страницы
│   ├── views/                # Страницы (MVVM View)
│   ├── viewmodels/           # ViewModel + TaskRunner (фоновые потоки)
│   ├── services/             # BackendService ABC + ProcurementBackend
│   └── components/           # DataTable, StatusBadge, ...
├── main.py                   # CLI: process, compare, demo, calibrate
├── gui_app.py                # GUI entry point
└── tests/                    # 153 теста (pytest)
```

**Поток:** Документ → Парсер → Нормализатор → Группировщик → Excel → Сравнение → Email

## Установка

```bash
git clone https://github.com/MaxAcrata/Procurement.git
cd Procurement
python -m venv .venv
.venv\Scripts\activate        # Windows
uv sync                       # или: pip install -e .
cp .env.example .env          # заполнить SMTP-credentials
```

### Docker

```bash
docker compose up --build
```

## Запуск

```bash
# GUI
python gui_app.py

# CLI
python main.py                                          # интерактивное меню
python main.py process file1.xlsx file2.pdf             # обработка документов
python main.py compare order.xlsx invoice.xlsx          # сравнение
python main.py calibrate --labels match_review.json     # калибровка порога
python main.py demo                                     # демо
```

### Сборка EXE

```bash
pyinstaller procurement.spec --clean --noconfirm
# Результат: dist/procurement.exe
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP-сервер |
| `SMTP_PORT` | `587` | SMTP-порт |
| `SMTP_USER` | — | Email для отправки |
| `SMTP_PASSWORD` | — | Пароль SMTP |
| `LOG_LEVEL` | `INFO` | Уровень логирования |

## Workflow (GUI)

1. **Файлы** — загрузить документы (drag & drop)
2. **Данные** — проверить товары (строки с низким OCR-confidence подсвечены)
3. **Поставщики** — проверить группировку
4. **Заказы** — сгенерировать заявки
5. **Сравнение** — заявка vs счета
6. **Ревью пар** — подтвердить/отклонить неоднозначные совпадения
7. **Email** — отправить заявки

## Сравнение артикулов

| Уровень | Вес | Описание |
|---------|-----|----------|
| Префикс | 0.4 | Первые N символов (по умолчанию 8) |
| Основной токен | 0.3 | Буквенно-цифровой блок |
| Числовые токены | 0.2 | Overlap числовых частей |
| Fuzzy | 0.1 | rapidfuzz similarity |

Порог: **0.75** (match). Gray-band: **0.5–0.75** (review). Ниже 0.5 — no_match.

```
71B3750 vs 71B3750         → 1.000 → MATCH
RT110GR.1/000/600 vs
RT110GR.1/128/150          → 0.464 → NO MATCH
```

Калибровка: `python main.py calibrate --labels match_review.json --apply`

## Тестирование

```bash
pytest tests/ -q                          # все тесты
pytest tests/ -q --cov=core --cov=parsers # с coverage
ruff check . && mypy --ignore-missing-imports core/ models/ config.py
```

## CI/CD

GitHub Actions: ruff → pytest → mypy → сборка (`.github/workflows/ci.yml`).

## Известные ограничения

- OCR: качество зависит от разрешения и языка изображения
- PDF: сложные макеты с объединёнными ячейками могут ломать парсинг
- Email: SMTP-credentials настраиваются в `.env`
- PyInstaller: сборка требует runtime-патчей для `six` + `shiboken6`
