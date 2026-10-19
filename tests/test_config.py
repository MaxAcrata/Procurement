"""Tests for application configuration."""

from config import settings, AppConfig, SmtpConfig, ArticleMatchConfig, RetryConfig


class TestAppConfig:
    def test_singleton_exists(self):
        assert settings is not None
        assert isinstance(settings, AppConfig)

    def test_smtp_config(self):
        assert isinstance(settings.smtp, SmtpConfig)
        assert settings.smtp.port == 587
        assert settings.smtp.use_tls is True

    def test_article_config(self):
        assert isinstance(settings.article, ArticleMatchConfig)
        assert settings.article.threshold == 0.75
        assert settings.article.prefix_length == 8

    def test_retry_config(self):
        assert isinstance(settings.retry, RetryConfig)
        assert settings.retry.max_retries == 3
        assert settings.retry.backoff_factor == 0.5
        assert settings.retry.timeout_seconds == 30.0

    def test_smtp_is_configured_property(self):
        configured = SmtpConfig(user="test@test.com", password="secret")
        assert configured.is_configured is True

        unconfigured = SmtpConfig(user="", password="")
        assert unconfigured.is_configured is False

    def test_config_is_frozen(self):
        import pytest
        with pytest.raises(AttributeError):
            settings.smtp.port = 999
