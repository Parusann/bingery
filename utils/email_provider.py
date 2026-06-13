"""Email providers for verification codes.

Mirrors utils/ai_provider.py: a small factory keyed on an env var, with a
console provider for dev/tests and Brevo (https://brevo.com) for production.
Brevo is called over plain HTTP via `requests` — no extra dependency.
"""
from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

import requests

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"

# Single source of truth for the code lifetime; routes/auth.py derives its
# CODE_TTL from this so the email copy can never drift from the real TTL.
CODE_TTL_MINUTES = 10


class EmailSendError(RuntimeError):
    """Raised when a verification email could not be sent.

    The register route catches this and returns a 503 so the user can
    simply retry — the pending signup row is kept.
    """


@runtime_checkable
class EmailProvider(Protocol):
    """What the auth routes need from a provider (mirrors AIProvider)."""

    def send_verification_code(self, to_email: str, code: str) -> None: ...


class ConsoleEmailProvider:
    """Dev/test provider: the 'email' is a log line."""

    def send_verification_code(self, to_email: str, code: str) -> None:
        logger.info("Verification code for %s: %s", to_email, code)


class BrevoEmailProvider:
    def __init__(self) -> None:
        self.api_key = os.environ.get("BREVO_API_KEY", "")
        self.from_email = os.environ.get("EMAIL_FROM", "")

    def send_verification_code(self, to_email: str, code: str) -> None:
        payload = {
            "sender": {"name": "Bingery", "email": self.from_email},
            "to": [{"email": to_email}],
            "subject": "Your Bingery verification code",
            "textContent": (
                f"Your Bingery verification code is {code}.\n\n"
                f"This code expires in {CODE_TTL_MINUTES} minutes. If you "
                "didn't create a Bingery account, you can ignore this email."
            ),
            "htmlContent": (
                "<div style=\"font-family:Arial,sans-serif;max-width:420px;"
                "margin:0 auto;padding:24px\">"
                "<h2 style=\"margin:0 0 12px\">Your Bingery verification code</h2>"
                f"<p style=\"font-size:32px;font-weight:bold;font-family:monospace;"
                f"letter-spacing:6px;margin:16px 0\">{code}</p>"
                f"<p style=\"color:#555\">This code expires in {CODE_TTL_MINUTES} "
                "minutes. If you didn't create a Bingery account, you can "
                "ignore this email.</p></div>"
            ),
        }
        try:
            resp = requests.post(
                BREVO_ENDPOINT,
                headers={"api-key": self.api_key, "content-type": "application/json"},
                json=payload,
                timeout=10,
            )
        except requests.exceptions.RequestException as exc:
            raise EmailSendError(f"Brevo unreachable: {type(exc).__name__}") from exc
        if not 200 <= resp.status_code < 300:
            # Brevo puts the actionable detail (bad key, unvalidated sender,
            # ...) in the body; keep it server-side for debugging.
            logger.error(
                "Brevo send failed: %s %s", resp.status_code, resp.text[:500]
            )
            raise EmailSendError(f"Brevo returned {resp.status_code}")


def get_email_provider() -> EmailProvider:
    """Return an email provider selected by the `EMAIL_PROVIDER` env var."""
    name = (os.getenv("EMAIL_PROVIDER") or "console").strip().lower()
    if name == "console":
        return ConsoleEmailProvider()
    if name == "brevo":
        return BrevoEmailProvider()
    raise ValueError(
        f"Unknown EMAIL_PROVIDER: {name!r}. Expected 'console' or 'brevo'."
    )
