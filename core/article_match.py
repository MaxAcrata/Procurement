"""Multi-level article matching with scoring system."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArticleConfig:
    """Configuration for article matching."""

    prefix_length: int = 8
    threshold: float = 0.75
    gray_band: tuple[float, float] = (0.5, 0.75)
    weight_prefix: float = 0.4
    weight_main_token: float = 0.3
    weight_numeric: float = 0.2
    weight_fuzzy: float = 0.1


@dataclass(frozen=True)
class ArticleTokens:
    """Parsed article tokens."""

    raw: str
    normalized: str
    prefix: str
    main_token: str
    numeric_tokens: tuple[str, ...]


# Module-level default config (immutable after creation)
_default_config = ArticleConfig()


def get_config() -> ArticleConfig:
    return _default_config


# ── Normalization ────────────────────────────────────────────────────────────


def normalize_article(article: str) -> str:
    """Normalize article: strip, remove separators, uppercase, keep alphanumeric."""
    if not article:
        return ""
    article = article.strip().replace(" ", "").replace("\xa0", "")
    article = re.sub(r"[/\-_.\\]+", "", article)
    return article.upper()


@lru_cache(maxsize=4096)
def tokenize_article(article: str) -> ArticleTokens:
    """Parse article into prefix, main token, and numeric parts (cached)."""
    normalized = normalize_article(article)

    prefix_match = re.match(r"^[A-Z]+", normalized)
    prefix = prefix_match.group(0) if prefix_match else ""

    main_match = re.match(r"^[A-Z0-9]+", normalized)
    main_token = main_match.group(0) if main_match else ""

    remaining = normalized[len(main_token) :] if main_token else normalized
    numeric_tokens = tuple(re.findall(r"\d+", remaining))

    return ArticleTokens(
        raw=article,
        normalized=normalized,
        prefix=prefix,
        main_token=main_token,
        numeric_tokens=numeric_tokens,
    )


# ── Scoring ──────────────────────────────────────────────────────────────────


def _numeric_overlap(a: ArticleTokens, b: ArticleTokens) -> float:
    if not a.numeric_tokens or not b.numeric_tokens:
        return 0.0
    set_a, set_b = set(a.numeric_tokens), set(b.numeric_tokens)
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 0.0


def _fuzzy_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz.fuzz import ratio as fuzzy_ratio
    except ImportError:
        from thefuzz.fuzz import ratio as fuzzy_ratio  # type: ignore[no-redef]
    return fuzzy_ratio(a, b) / 100.0


def calculate_score(
    article_a: str,
    article_b: str,
    config: ArticleConfig | None = None,
) -> float:
    """Calculate match score between two articles (0.0 – 1.0)."""
    if not article_a or not article_b:
        return 0.0

    cfg = config or _default_config
    tokens_a = tokenize_article(article_a)
    tokens_b = tokenize_article(article_b)

    # Exact normalized match
    if tokens_a.normalized == tokens_b.normalized:
        return 1.0

    # Prefix
    prefix_len = min(cfg.prefix_length, len(tokens_a.prefix), len(tokens_b.prefix))
    prefix_score = 1.0 if prefix_len >= 2 and tokens_a.prefix[:prefix_len] == tokens_b.prefix[:prefix_len] else 0.0

    # Main token
    main_score = 1.0 if tokens_a.main_token == tokens_b.main_token else 0.0

    # Numeric overlap
    numeric_score = _numeric_overlap(tokens_a, tokens_b)

    # Fuzzy
    fuzzy_score_val = _fuzzy_score(tokens_a.normalized, tokens_b.normalized)

    total = (
        prefix_score * cfg.weight_prefix
        + main_score * cfg.weight_main_token
        + numeric_score * cfg.weight_numeric
        + fuzzy_score_val * cfg.weight_fuzzy
    )

    logger.debug(
        "SCORE: %s vs %s → %.3f (prefix=%.1f main=%.1f num=%.2f fuzzy=%.2f)",
        article_a,
        article_b,
        total,
        prefix_score,
        main_score,
        numeric_score,
        fuzzy_score_val,
    )
    return total


def compare_articles(
    article_a: str,
    article_b: str,
    config: ArticleConfig | None = None,
) -> bool:
    """Return True if two articles match above the threshold."""
    cfg = config or _default_config
    score = calculate_score(article_a, article_b, cfg)
    match = score >= cfg.threshold
    logger.debug(
        "DECISION: %s vs %s → %.3f >= %.2f → %s", article_a, article_b, score, cfg.threshold, "MATCH" if match else "NO"
    )
    return match


def classify(score: float, config: ArticleConfig | None = None) -> str:
    """Classify a match score as 'match' | 'review' | 'no_match'."""
    cfg = config or _default_config
    if score >= cfg.threshold:
        return "match"
    if score >= cfg.gray_band[0]:
        return "review"
    return "no_match"
