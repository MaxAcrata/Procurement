"""Core business logic: article matching, normalization, comparison, grouping."""

from core.article_match import (
    ArticleConfig,
    ArticleTokens,
    normalize_article,
    tokenize_article,
    calculate_score,
    compare_articles,
)

__all__ = [
    "ArticleConfig",
    "ArticleTokens",
    "normalize_article",
    "tokenize_article",
    "calculate_score",
    "compare_articles",
]
