"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys

from config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)-7s | %(name)-28s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        stream=sys.stderr,
        force=True,
    )

    # Quieten noisy third-party loggers
    for name in ("urllib3", "httpx", "httpcore", "openpyxl"):
        logging.getLogger(name).setLevel(logging.WARNING)
