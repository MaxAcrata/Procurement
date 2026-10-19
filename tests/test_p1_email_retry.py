"""Regression tests for P1 fixes.

P1-retry: SMTP retry must back off exponentially using RetryConfig
          (backoff_factor between attempts, timeout_seconds on connect).
P1-email: supplier emails must be validated before persisting/sending.
"""

from __future__ import annotations

import time

import pytest

# ── helpers ─────────────────────────────────────────────────────────────────


class _RecordingSMTP:
    """Stand-in for smtplib.SMTP; fails `fail_times` first connections/sends."""

    instances: list[dict] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        type(self).instances.append({"host": host, "port": port, "timeout": timeout})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, timeout=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        raise ConnectionError("boom")


def _fake_settings_retry(monkeypatch, max_retries=3, backoff_factor=0.5, timeout_seconds=30.0):
    """Patch the settings.retry values read by mailer.sender."""
    import mailer.sender as sender_mod

    class _Retry:
        pass

    retry = _Retry()
    retry.max_retries = max_retries
    retry.backoff_factor = backoff_factor
    retry.timeout_seconds = timeout_seconds

    class _Settings:
        pass

    settings = _Settings()
    settings.smtp = sender_mod.settings.smtp
    settings.retry = retry
    monkeypatch.setattr(sender_mod, "settings", settings)
    return settings


# ── P1-retry ────────────────────────────────────────────────────────────────


def test_retry_uses_exponential_backoff_between_attempts(monkeypatch):
    """Failing sends must pause backoff_factor * 2**(attempt-1) between tries."""
    import mailer.sender as sender_mod

    _fake_settings_retry(monkeypatch, max_retries=3, backoff_factor=0.5)

    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    class _FailSMTP(_RecordingSMTP):
        instances = []

        def send_message(self, msg):
            raise ConnectionError("boom")

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _FailSMTP)

    result = sender_mod.send_email(
        to="a@b.co",
        subject="s",
        body="b",
        smtp_user="user",
        smtp_password="pass",
    )

    assert result["status"] == "error"
    assert sleeps == [0.5, 1.0], f"expected exponential backoff, got {sleeps}"
    assert len(_FailSMTP.instances) == 3


def test_retry_success_after_failures_still_backs_off(monkeypatch):
    """Sleep happens only between attempts; success on last try returns success."""
    import mailer.sender as sender_mod

    _fake_settings_retry(monkeypatch, max_retries=3, backoff_factor=0.5)

    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

    class _FlakySMTP(_RecordingSMTP):
        instances = []
        attempts = 0

        def send_message(self, msg):
            type(self).attempts += 1
            if type(self).attempts < 3:
                raise ConnectionError("boom")

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _FlakySMTP)

    result = sender_mod.send_email(
        to="a@b.co",
        subject="s",
        body="b",
        smtp_user="user",
        smtp_password="pass",
    )

    assert result["status"] == "success"
    assert sleeps == [0.5, 1.0]


def test_smtp_connect_uses_configured_timeout(monkeypatch):
    """Connection timeout must come from RetryConfig.timeout_seconds."""
    import mailer.sender as sender_mod

    _fake_settings_retry(monkeypatch, timeout_seconds=12.0)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    class _OkSMTP(_RecordingSMTP):
        instances = []

        def send_message(self, msg):
            pass

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _OkSMTP)

    result = sender_mod.send_email(
        to="a@b.co",
        subject="s",
        body="b",
        smtp_user="user",
        smtp_password="pass",
    )

    assert result["status"] == "success"
    assert _OkSMTP.instances[0]["timeout"] == 12.0


# ── P1-email validation ─────────────────────────────────────────────────────


def test_update_email_rejects_invalid_address():
    """Invalid addresses must raise and must not be persisted."""
    from gui.services.backend_impl import ProcurementBackend

    backend = ProcurementBackend()
    backend._emails = {"Blum": "old@example.com"}

    with pytest.raises(ValueError):
        backend.update_email("Blum", "not-an-email")

    assert backend.get_emails() == {"Blum": "old@example.com"}


def test_update_email_rejects_partial_address():
    """Partial input (typo/unfinished) must not replace a stored address."""
    from gui.services.backend_impl import ProcurementBackend

    backend = ProcurementBackend()
    backend._emails = {"Blum": "old@example.com"}

    with pytest.raises(ValueError):
        backend.update_email("Blum", "blum@")

    assert backend.get_emails() == {"Blum": "old@example.com"}


def test_update_email_accepts_valid_address():
    from gui.services.backend_impl import ProcurementBackend

    backend = ProcurementBackend()
    backend.update_email("Blum", "new@example.com")

    assert backend.get_emails() == {"Blum": "new@example.com"}


def test_update_email_allows_clearing_with_empty_string():
    """Empty string clears the address (no validation error)."""
    from gui.services.backend_impl import ProcurementBackend

    backend = ProcurementBackend()
    backend._emails = {"Blum": "old@example.com"}
    backend.update_email("Blum", "")

    assert backend.get_emails() == {"Blum": ""}


def test_send_email_rejects_invalid_recipient(monkeypatch):
    """send_email must not contact SMTP for a malformed recipient."""
    import mailer.sender as sender_mod

    contacted = []

    class _BoomSMTP:
        def __init__(self, *args, **kwargs):
            contacted.append(args)
            raise AssertionError("SMTP must not be contacted for invalid recipient")

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _BoomSMTP)

    result = sender_mod.send_email(
        to="not-an-email",
        subject="s",
        body="b",
        smtp_user="user",
        smtp_password="pass",
    )

    assert result["status"] == "error"
    assert "not-an-email" in result["message"]
    assert contacted == []


# ── GUI feedback on validation failure ──────────────────────────────────────


def test_email_vm_emits_error_and_restores_state_on_invalid_email():
    """Invalid input must surface an error and re-sync the view with stored state."""
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.email_vm import EmailViewModel

    backend = ProcurementBackend()
    backend._emails = {"Blum": "old@example.com"}
    vm = EmailViewModel(backend)
    vm.refresh()

    errors: list[str] = []
    vm.error_occurred.connect(errors.append)
    refreshes: list[int] = []
    vm.data_changed.connect(lambda: refreshes.append(1))

    vm.update_email("Blum", "bad-address")

    assert errors and "bad-address" in errors[0]
    assert refreshes, "failed update must emit data_changed so the view restores stored state"
    assert vm.emails == {"Blum": "old@example.com"}
