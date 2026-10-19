# Procurement Agent

Автоматизация закупочного процесса: парсинг документов, группировка по поставщикам, формирование заявок, сравнение с счетами.

## Возможности

- Парсинг документов: PDF, XLSX, DOCX, изображения (OCR)
- Автоматическое определение столбцов (наименование, артикул, количество, поставщик)
- Нормализация данных (исправление ошибок OCR, унификация артикулов)
- Многоуровневое сравнение артикулов с scoring-системой
- Группировка товаров по поставщикам
- Генерация Excel-заявок (формат: `<поставщик>_<дд.мм.гггг>.xlsx`)
- Сравнение заявки со счетами (артикул + количество)
- Отправка email поставщикам с вложениями (с retry и timeout)
- GUI с навигацией (PySide6, тёмная тема)
- CLI-режим для автоматизации
- Структурированное логирование
- Единый конфигурационный модуль

## Архитектура

```
procurement_agent/
├── config.py                 # Единый конфиг (SMTP, article matching, retry)
├── logging_setup.py          # Структурированное логирование
├── models/                   # Данные: Product, ComparisonItem, SupplierGroup
├── core/
│   ├── article_match.py      # Сравнение артикулов (normalize → tokenize → score)
│   ├── normalizer.py         # Нормализация и дедупликация
│   ├── comparator.py         # Сравнение заявки со счетом
│   └── grouper.py            # Группировка по поставщикам
├── parsers/
│   ├── utils.py              # Общие утилиты (parse_quantity, map_columns)
│   ├── xlsx_parser.py        # Excel (pandas + openpyxl)
│   ├── pdf_parser.py         # PDF (pdfplumber)
│   ├── docx_parser.py        # Word (python-docx)
│   └── image_parser.py       # Изображения (pytesseract OCR)
├── generators/
│   └── excel_gen.py          # Генерация Excel-файлов
├── mailer/
│   └── sender.py             # Отправка email (SMTP + retry)
├── gui/
│   ├── main_window.py        # Главное окно (PySide6)
│   ├── views/                # Страницы GUI
│   ├── viewmodels/           # ViewModel-слой (MVVM)
│   ├── components/           # Переиспользуемые виджеты
│   ├── services/
│   │   ├── backend_interface.py  # Абстракция (ABC)
│   │   └── backend_impl.py       # Реализация
│   └── styles/               # QSS тёмная тема
├── tests/                    # Unit + integration тесты
├── hooks/                    # Runtime-хуки для PyInstaller
├── Dockerfile                # Docker-образ
├── docker-compose.yml        # Docker Compose
├── .github/workflows/ci.yml  # CI/CD (GitHub Actions)
├── .pre-commit-config.yaml   # Pre-commit хуки
└── pyproject.toml            # Конфигурация проекта
```

**Поток данных:**

```
Документ → Парсер → Нормализатор → Группировщик → Генератор Excel
                                       ↓
                              Сравнитель (заявка vs счет)
                                       ↓
                              Email-отправка (с retry)
```

## Установка

```bash
# Клонировать репозиторий
git clone <url>
cd procurement_agent

# Создать виртуальное окружение
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Установить зависимости (рекомендуется uv)
pip install uv
uv sync

# Или через pip
pip install -e .
```

### Docker

```bash
docker compose up --build
```

### Зависимости

| Пакет | Версия | Назначение |
|-------|--------|------------|
| PySide6 | >=6.11.1 | GUI |
| pandas | >=3.0.3 | Парсинг XLSX |
| openpyxl | >=3.1.5 | Чтение/запись Excel |
| pdfplumber | >=0.11.10 | Парсинг PDF |
| python-docx | >=1.2.0 | Парсинг DOCX |
| Pillow | >=12.3.0 | Обработка изображений |
| thefuzz | >=0.22.1 | Нечёткое сравнение |
| rapidfuzz | >=3.0.0 | Быстрое нечёткое сравнение |
| python-dotenv | >=1.2.2 | Переменные окружения |
| rich | >=15.0.0 | CLI-вывод |
| typer | >=0.26.8 | CLI-фреймворк |
| lxml | >=5.0.0 | XML-парсинг |

## Запуск

### GUI

```bash
python gui_app.py
```

### CLI

```bash
# Интерактивное меню
python main.py

# Обработка документов
python main.py process file1.xlsx file2.pdf --output-dir output

# Сравнение заявки со счетом
python main.py compare order.xlsx invoice.xlsx --output report.xlsx

# Демо
python main.py demo
```

### EXE (сборка)

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

## Конфигурация

### Сравнение артикулов

```python
from core.article_match import ArticleConfig, calculate_score

config = ArticleConfig(prefix_length=8, threshold=0.75)
score = calculate_score("ABC-123", "ABC-123", config)
```

### Настройка retry

```python
from config import settings
# settings.retry.max_retries = 5
# settings.retry.timeout_seconds = 60
```

## Тестирование

```bash
# Все тесты
pytest tests/ -v

# С coverage
pytest tests/ -v --cov=core --cov=parsers --cov=generators

# Только unit-тесты
pytest tests/test_article_match.py tests/test_normalizer.py -v
```

## Линтинг

```bash
# Ruff
ruff check .
ruff format .

# MyPy
mypy --ignore-missing-imports core/ models/ config.py
```

## CI/CD

GitHub Actions автоматически:
- Линтит код (ruff)
- Запускает тесты (pytest)
- Проверяет типы (mypy)
- Собирает пакет

См. `.github/workflows/ci.yml`.

## Использование

### Workflow пользователя (GUI)

1. **Файлы** — загрузить документы (drag & drop или выбор файлов)
2. **Данные** — проверить распознанные товары, отфильтровать по поставщику
3. **Поставщики** — проверить группировку, при необходимости переименовать поставщика
4. **Заказы** — выбрать папку для сохранения, сгенерировать заявки
5. **Сравнение** — выбрать заявку и счета, нажать "Сравнить"
6. **Email** — отправить заявки поставщикам

### Формат входных данных

**PDF-таблицы** — извлекаются автоматически. Столбцы определяются по заголовкам (наименование, артикул, количество).

**XLSX** — три стратегии определения столбцов:
1. По заголовкам (Наименование, Артикул, Количество, Поставщик)
2. По содержимому (числа → количество, короткий текст → артикул, длинный → наименование)
3. По позиции (fallback: столбец 0=наименование, 1=артикул, 2=количество)

**DOCX** — сначала таблицы, затем параграфы с regex-парсингом.

**Изображения** — OCR через Tesseract (русский + английский). Формат: `Наименование Артикул:XXX Кол-во:N`.

### Формат выходных данных

**Заявка** (`<поставщик>_<дд.мм.гггг>.xlsx`):

| Наименование | Артикул | Дата |
|---|---|---|
| Петля Blumotion | 71B3750 | 10.07.2026 |

**Отчёт сравнения** (`comparison_report.xlsx`):

| Наименование | Артикул | Кол-во (заявка) | Кол-во (счет) | Статус | Разница |
|---|---|---|---|---|---|
| Ручка | ABC-123 | 10 | 15 | Расхождение | 5 |

## Сравнение артикулов

Многоуровневая scoring-система:

| Уровень | Вес | Описание |
|---------|-----|----------|
| Префикс | 0.4 | Первые N символов (по умолчанию 8) |
| Основной токен | 0.3 | Буквенно-цифровой блок |
| Числовые токены | 0.2 | overlap числовых частей |
| Fuzzy | 0.1 | rapidfuzz similarity |

Порог совпадения: **0.75** (настраивается через `ArticleConfig`).

```
71B3750 vs 71B3750         → 1.000 → MATCH
RT110GR.1/000/600 vs
RT110GR.1/128/150          → 0.464 → NO MATCH
```

## Известные проблемы и ограничения

- **OCR**: качество зависит от разрешения изображения и языка
- **PDF-таблицы**: сложные макеты (объединённые ячейки) могут ломать парсинг
- **Артикулы**: PDF-файлы иногда содержат лишний текст в ячейке артикула (автоочистка работает, но не всегда)
- **Дубликаты**: нормализация объединяет товары с одинаковым артикулом в пределах одного поставщика
- **Email**: SMTP-credentials должны быть настроены в `.env`
- **PyInstaller**: сборка требует ручного патча для `six` + `shiboken6`
