"""Application configuration — single source of truth."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
EMAILS_DB_PATH = PROJECT_ROOT / "emails_db.json"

# ── SMTP ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SmtpConfig:
    host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    use_tls: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.user and self.password)

# ── Article matching ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ArticleMatchConfig:
    prefix_length: int = 8
    threshold: float = 0.75
    weight_prefix: float = 0.4
    weight_main_token: float = 0.3
    weight_numeric: float = 0.2
    weight_fuzzy: float = 0.1

# ── Retry / timeout ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    backoff_factor: float = 0.5
    timeout_seconds: float = 30.0

# ── Application ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AppConfig:
    smtp: SmtpConfig = field(default_factory=SmtpConfig)
    article: ArticleMatchConfig = field(default_factory=ArticleMatchConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    emails_db_path: Path = EMAILS_DB_PATH
    output_dir: Path = OUTPUT_DIR
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Singleton — import and use directly
settings = AppConfig()
