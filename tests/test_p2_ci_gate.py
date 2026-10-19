"""Integration fixes blocking the CI mypy gate (P2-16).

1. smtplib.SMTP.starttls accepts only ``context`` — passing ``timeout`` raises
   TypeError at runtime (typeshed call-arg error was a real bug).
2. core/article_match._fuzzy_score re-imports ``ratio`` in the except branch
   (mypy no-redef) — behavior unchanged, fixed for the gate.
"""

from __future__ import annotations


def test_starttls_called_without_timeout_kwarg(monkeypatch):
    """starttls must be invoked with the real smtplib signature (context only)."""
    import mailer.sender as sender_mod

    class _SMTP:
        def __init__(self, host, port, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, *, context=None):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            pass

    monkeypatch.setattr(sender_mod.smtplib, "SMTP", _SMTP)

    result = sender_mod.send_email(
        to="a@b.co",
        subject="s",
        body="b",
        smtp_user="user",
        smtp_password="pass",
    )

    assert result["status"] == "success"


def test_fuzzy_score_works_with_single_ratio_binding():
    """_fuzzy_score must still return a ratio after the no-redef cleanup."""
    from core.article_match import _fuzzy_score

    assert _fuzzy_score("ABC123", "ABC123") == 1.0
    assert 0.0 <= _fuzzy_score("ABC123", "XYZ999") < 1.0
