"""Core business logic: article matching, normalization, comparison, grouping."""

from core.article_match import (
    ArticleConfig,
    ArticleTokens,
    calculate_score,
    compare_articles,
    normalize_article,
    tokenize_article,
)

__all__ = [
    "ArticleConfig",
    "ArticleTokens",
    "calculate_score",
    "compare_articles",
    "normalize_article",
    "tokenize_article",
]
