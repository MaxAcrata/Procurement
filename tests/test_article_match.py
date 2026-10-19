"""Unit tests for article matching system."""

from core.article_match import (
    normalize_article,
    tokenize_article,
    compare_articles,
    calculate_score,
    ArticleConfig,
)


class TestNormalizeArticle:
    def test_removes_slashes(self):
        assert normalize_article("RT110GR.1/000/600") == "RT110GR1000600"

    def test_removes_dots(self):
        assert normalize_article("70.1503.BP") == "701503BP"

    def test_removes_dashes(self):
        assert normalize_article("ABC-123") == "ABC123"

    def test_removes_underscores(self):
        assert normalize_article("ABC_123") == "ABC123"

    def test_uppercase(self):
        assert normalize_article("abc-123") == "ABC123"

    def test_removes_spaces(self):
        assert normalize_article("2574 20") == "257420"

    def test_empty(self):
        assert normalize_article("") == ""

    def test_none_returns_empty(self):
        assert normalize_article(None) == ""


class TestTokenizeArticle:
    def test_prefix(self):
        tokens = tokenize_article("RT110GR.1/000/600")
        # After normalization: "RT110GR1000600"
        assert tokens.prefix == "RT"
        assert tokens.main_token == "RT110GR1000600"
        assert tokens.numeric_tokens == ()

    def test_letters_only(self):
        tokens = tokenize_article("BLUM")
        assert tokens.prefix == "BLUM"
        assert tokens.main_token == "BLUM"
        assert tokens.numeric_tokens == ()

    def test_digits_only(self):
        tokens = tokenize_article("12345")
        assert tokens.prefix == ""
        assert tokens.main_token == "12345"
        assert tokens.numeric_tokens == ()

    def test_complex(self):
        tokens = tokenize_article("MHB.C07.BV.1L.10")
        # After normalization: "MHBC07BV1L10"
        assert tokens.prefix == "MHBC"
        assert tokens.main_token == "MHBC07BV1L10"
        assert tokens.numeric_tokens == ()


class TestCompareArticles:
    def test_exact_match(self):
        assert compare_articles("RT110GR.1/000/600", "RT110GR.1/000/600") is True

    def test_different_articles_no_match(self):
        assert compare_articles("RT110GR.1/000/600", "RT110GR.1/128/150") is False

    def test_similar_prefix_different_suffix(self):
        assert compare_articles("71B3750", "71B3550") is False

    def test_completely_different(self):
        assert compare_articles("ABC-123", "XYZ-789") is False

    def test_same_after_normalization(self):
        assert compare_articles("abc-123", "ABC123") is True

    def test_empty_articles(self):
        assert compare_articles("", "ABC") is False
        assert compare_articles("ABC", "") is False
        assert compare_articles("", "") is False


class TestScore:
    def test_exact_score(self):
        score = calculate_score("ABC-123", "ABC-123")
        assert score == 1.0

    def test_different_scores_low(self):
        score = calculate_score("RT110GR.1/000/600", "RT110GR.1/128/150")
        assert score < 0.75

    def test_similar_prefix_scores(self):
        score = calculate_score("71B3750", "71B3550")
        # After normalization both start with digits → no prefix match
        # Main tokens differ ("71B3750" vs "71B3550") → main_score=0
        # Only fuzzy contributes (~0.85 * 0.1 = 0.085)
        assert score < 0.75


class TestConfig:
    def test_custom_threshold(self):
        config = ArticleConfig(threshold=0.9)
        assert compare_articles("ABC-123", "ABC-123", config) is True
        assert compare_articles("ABC-123", "ABC-456", config) is False

    def test_custom_prefix_length(self):
        config = ArticleConfig(prefix_length=4)
        score = calculate_score("RT110GR.1/000/600", "RT110GR.1/128/150", config)
        assert score < 0.75


class TestRealCases:
    def test_bug_scenario_1(self):
        assert compare_articles("RT110GR.1/000/600", "RT110GR.1/128/150") is False

    def test_bug_scenario_2(self):
        assert compare_articles("71B3750", "71B3750") is True

    def test_different_suppliers_same_article(self):
        score = calculate_score("ABC-123", "ABC-123")
        assert score == 1.0
