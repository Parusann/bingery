"""Email providers for verification codes.

Mirrors utils/ai_provider.py: a small factory keyed on an env var, with a
console provider for dev/tests and Brevo (https://brevo.com) for production.
Brevo is called over plain HTTP via `requests` — no extra dependency.
"""
from __future__ import annotations

import html
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
    """What the auth + waitlist routes need from a provider."""

    def send_verification_code(self, to_email: str, code: str) -> None: ...

    def send_waitlist_confirmation(self, to_email: str) -> None: ...

    def send_waitlist_owner_alert(self, signup_email: str) -> None: ...


class ConsoleEmailProvider:
    """Dev/test provider: the 'email' is a log line."""

    def send_verification_code(self, to_email: str, code: str) -> None:
        logger.info("Verification code for %s: %s", to_email, code)

    def send_waitlist_confirmation(self, to_email: str) -> None:
        logger.info("Waitlist confirmation for %s", to_email)

    def send_waitlist_owner_alert(self, signup_email: str) -> None:
        logger.info("Waitlist owner alert: %s joined the waitlist", signup_email)


class BrevoEmailProvider:
    def __init__(self) -> None:
        self.api_key = os.environ.get("BREVO_API_KEY", "")
        self.from_email = os.environ.get("EMAIL_FROM", "")

    def _send(
        self, to_email: str, subject: str, text_content: str, html_content: str
    ) -> None:
        payload = {
            "sender": {"name": "Bingery", "email": self.from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": text_content,
            "htmlContent": html_content,
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

    def send_verification_code(self, to_email: str, code: str) -> None:
        self._send(
            to_email,
            "Your Bingery verification code",
            (
                f"Your Bingery verification code is {code}.\n\n"
                f"This code expires in {CODE_TTL_MINUTES} minutes. If you "
                "didn't create a Bingery account, you can ignore this email."
            ),
            (
                "<div style=\"font-family:Arial,sans-serif;max-width:420px;"
                "margin:0 auto;padding:24px\">"
                "<h2 style=\"margin:0 0 12px\">Your Bingery verification code</h2>"
                f"<p style=\"font-size:32px;font-weight:bold;font-family:monospace;"
                f"letter-spacing:6px;margin:16px 0\">{code}</p>"
                f"<p style=\"color:#555\">This code expires in {CODE_TTL_MINUTES} "
                "minutes. If you didn't create a Bingery account, you can "
                "ignore this email.</p></div>"
            ),
        )

    def send_waitlist_confirmation(self, to_email: str) -> None:
        self._send(
            to_email,
            "You're on the Bingery waitlist",
            (
                "Thanks for your interest in Bingery! You're on the waitlist — "
                "we'll email you the moment a spot opens up."
            ),
            (
                "<div style=\"font-family:Arial,sans-serif;max-width:420px;"
                "margin:0 auto;padding:24px\">"
                "<h2 style=\"margin:0 0 12px\">You're on the Bingery waitlist</h2>"
                "<p style=\"color:#555\">Thanks for your interest in Bingery! "
                "We'll email you the moment a spot opens up.</p></div>"
            ),
        )

    def send_waitlist_owner_alert(self, signup_email: str) -> None:
        # Read at call time (not __init__) so the alert can be turned on/off
        # without touching code; unset simply means "don't alert".
        owner = os.environ.get("WAITLIST_ALERT_EMAIL", "").strip()
        if not owner:
            logger.info(
                "WAITLIST_ALERT_EMAIL not set; skipping waitlist owner alert"
            )
            return
        # The signup email is attacker-controlled (the route regex allows
        # < and >), so it must not land in the HTML body unescaped.
        safe_email = html.escape(signup_email)
        self._send(
            owner,
            "New Bingery waitlist signup",
            f"{signup_email} just joined the Bingery waitlist.",
            (
                "<div style=\"font-family:Arial,sans-serif;max-width:420px;"
                "margin:0 auto;padding:24px\">"
                "<h2 style=\"margin:0 0 12px\">New waitlist signup</h2>"
                f"<p style=\"color:#555\"><strong>{safe_email}</strong> "
                "just joined the Bingery waitlist.</p></div>"
            ),
        )


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
