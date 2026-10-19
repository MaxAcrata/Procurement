"""Email sending with retry, timeout, and structured error handling."""

from __future__ import annotations

import logging
import re
import smtplib
import socket
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_FILENAME_UNSAFE_RE = re.compile(r'[\x00-\x1f\x7f"\\]')


def _sanitize_filename(name: str) -> str:
    """Strip quotes and control characters that could break or inject MIME headers."""
    return _FILENAME_UNSAFE_RE.sub("", name) or "attachment"


def is_valid_email(value: str) -> bool:
    """Return True if value is a syntactically valid email address."""
    return bool(_EMAIL_RE.match(value))


def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[Path] | None = None,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    use_tls: bool = True,
    timeout: float | None = None,
) -> dict[str, str]:
    """Send an email with optional attachments and retry logic."""
    cfg = settings.smtp
    host = smtp_host or cfg.host
    port = smtp_port or cfg.port
    user = smtp_user or cfg.user
    password = smtp_password or cfg.password

    if not is_valid_email(to):
        return {"status": "error", "message": f"Invalid recipient address: {to}"}

    if not user or not password:
        return {"status": "error", "message": "SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD."}

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachments:
        for file_path in attachments:
            if not file_path.exists():
                logger.warning("Attachment not found, skipping: %s", file_path)
                continue
            with open(file_path, "rb") as f:
                safe_name = _sanitize_filename(file_path.name)
                part = MIMEApplication(f.read(), Name=safe_name)
                part["Content-Disposition"] = f'attachment; filename="{safe_name}"'
                msg.attach(part)

    effective_timeout = timeout if timeout is not None else settings.retry.timeout_seconds
    max_retries = settings.retry.max_retries
    backoff_factor = settings.retry.backoff_factor

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP(host, port, timeout=effective_timeout) as server:
                if use_tls:
                    server.starttls()
                server.login(user, password)
                server.send_message(msg)
            logger.info("Email sent to %s (attempt %d)", to, attempt)
            return {"status": "success", "message": f"Email sent to {to}"}
        except (smtplib.SMTPException, socket.timeout, ConnectionError, OSError) as e:
            last_error = e
            logger.warning("Email send attempt %d failed: %s", attempt, e)
            if attempt < max_retries:
                delay = backoff_factor * (2 ** (attempt - 1))
                logger.info("Retrying in %.1fs", delay)
                time.sleep(delay)

    logger.error("Failed to send email to %s after %d attempts: %s", to, max_retries, last_error)
    return {"status": "error", "message": f"Failed to send email: {last_error}"}


def send_purchase_order_email(
    to: str,
    supplier_name: str,
    attachment_path: Path,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
) -> dict[str, str]:
    """Send a purchase order email to a supplier."""
    if not attachment_path or not Path(attachment_path).exists():
        return {"status": "error", "message": f"Attachment not found: {attachment_path}"}

    subject = "Заявка на закупку"
    body = (
        f"Уважаемые коллеги,\n\n"
        f"Направляем заявку на закупку.\n\n"
        f"Поставщик: {supplier_name}\n\n"
        f"Прошу рассмотреть и подтвердить возможность поставки.\n\n"
        f"С уважением,\n"
        f"Отдел закупок"
    )

    return send_email(
        to=to,
        subject=subject,
        body=body,
        attachments=[attachment_path] if attachment_path else None,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
    )
