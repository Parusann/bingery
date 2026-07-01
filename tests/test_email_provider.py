"""Tests for utils/email_provider.py — console + Brevo providers and factory."""
import logging

import pytest
import requests
import responses

from utils.email_provider import (
    BrevoEmailProvider,
    ConsoleEmailProvider,
    EmailSendError,
    get_email_provider,
)


def test_console_provider_logs_code(caplog):
    provider = ConsoleEmailProvider()
    with caplog.at_level(logging.INFO):
        provider.send_verification_code("someone@example.com", "123456")
    assert "someone@example.com" in caplog.text
    assert "123456" in caplog.text


def test_factory_defaults_to_console(monkeypatch):
    monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
    assert isinstance(get_email_provider(), ConsoleEmailProvider)


def test_factory_selects_brevo(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    assert isinstance(get_email_provider(), BrevoEmailProvider)


def test_factory_rejects_unknown(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "pigeon")
    with pytest.raises(ValueError):
        get_email_provider()


@responses.activate
def test_brevo_sends_expected_payload(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"messageId": "x"},
        status=201,
    )
    BrevoEmailProvider().send_verification_code("someone@example.com", "654321")

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["api-key"] == "test-key"
    body = req.body.decode() if isinstance(req.body, bytes) else req.body
    assert "654321" in body
    assert "someone@example.com" in body
    assert "codes@example.com" in body


@responses.activate
def test_brevo_non_2xx_raises(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"message": "bad key"},
        status=401,
    )
    with pytest.raises(EmailSendError):
        BrevoEmailProvider().send_verification_code("someone@example.com", "654321")


@responses.activate
def test_brevo_non_2xx_logs_response_body(monkeypatch, caplog):
    """Brevo puts the actionable error detail in the response body — it must
    land in the server log, not be discarded."""
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"code": "unauthorized", "message": "Key not found"},
        status=401,
    )
    with caplog.at_level(logging.ERROR):
        with pytest.raises(EmailSendError):
            BrevoEmailProvider().send_verification_code("someone@example.com", "654321")
    assert "401" in caplog.text
    assert "Key not found" in caplog.text


@responses.activate
def test_brevo_copy_derives_ttl_from_shared_constant(monkeypatch):
    """The expiry wording must come from CODE_TTL_MINUTES, not a literal."""
    import utils.email_provider as ep

    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    assert getattr(ep, "CODE_TTL_MINUTES", None) is not None
    monkeypatch.setattr(ep, "CODE_TTL_MINUTES", 7)
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"messageId": "x"},
        status=201,
    )
    ep.BrevoEmailProvider().send_verification_code("someone@example.com", "654321")
    req = responses.calls[0].request
    body = req.body.decode() if isinstance(req.body, bytes) else req.body
    assert "expires in 7 minutes" in body
    assert "10 minutes" not in body


def test_route_ttl_matches_email_copy_constant():
    from datetime import timedelta

    from routes.auth import CODE_TTL
    from utils.email_provider import CODE_TTL_MINUTES

    assert CODE_TTL == timedelta(minutes=CODE_TTL_MINUTES)


def test_providers_satisfy_email_provider_protocol():
    """Both providers must satisfy the EmailProvider Protocol, mirroring the
    AIProvider pattern in utils/ai_provider.py."""
    from utils.email_provider import EmailProvider

    assert isinstance(ConsoleEmailProvider(), EmailProvider)
    assert isinstance(BrevoEmailProvider(), EmailProvider)


@responses.activate
def test_brevo_network_error_raises(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        body=requests.exceptions.ConnectionError("boom"),
    )
    with pytest.raises(EmailSendError):
        BrevoEmailProvider().send_verification_code("someone@example.com", "654321")


def test_console_provider_logs_waitlist_confirmation(caplog):
    provider = ConsoleEmailProvider()
    with caplog.at_level(logging.INFO):
        provider.send_waitlist_confirmation("fan@example.com")
    assert "fan@example.com" in caplog.text


def test_console_provider_logs_waitlist_owner_alert(caplog):
    provider = ConsoleEmailProvider()
    with caplog.at_level(logging.INFO):
        provider.send_waitlist_owner_alert("fan@example.com")
    assert "fan@example.com" in caplog.text


@responses.activate
def test_brevo_sends_waitlist_owner_alert_to_configured_owner(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "hello@example.com")
    monkeypatch.setenv("WAITLIST_ALERT_EMAIL", "owner@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"messageId": "x"},
        status=201,
    )
    BrevoEmailProvider().send_waitlist_owner_alert("fan@example.com")

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    body = req.body.decode() if isinstance(req.body, bytes) else req.body
    assert "owner@example.com" in body  # the alert goes to the owner
    assert "fan@example.com" in body  # ...and names the signup
    assert "waitlist" in body.lower()


@responses.activate
def test_brevo_owner_alert_escapes_html_in_signup_email(monkeypatch):
    """The signup email is attacker-controlled (the route regex allows < >),
    so it must be HTML-escaped in the owner alert's HTML body."""
    import json

    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "hello@example.com")
    monkeypatch.setenv("WAITLIST_ALERT_EMAIL", "owner@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"messageId": "x"},
        status=201,
    )
    BrevoEmailProvider().send_waitlist_owner_alert("<b>x</b>@example.com")

    req = responses.calls[0].request
    body = req.body.decode() if isinstance(req.body, bytes) else req.body
    html = json.loads(body)["htmlContent"]
    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;@example.com" in html


@responses.activate
def test_brevo_owner_alert_skipped_when_recipient_unset(monkeypatch):
    """No WAITLIST_ALERT_EMAIL → no HTTP call and no exception; the signup
    itself must never depend on the alert being configured."""
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "hello@example.com")
    monkeypatch.delenv("WAITLIST_ALERT_EMAIL", raising=False)
    BrevoEmailProvider().send_waitlist_owner_alert("fan@example.com")
    assert len(responses.calls) == 0


@responses.activate
def test_brevo_sends_waitlist_confirmation(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "hello@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        json={"messageId": "x"},
        status=201,
    )
    BrevoEmailProvider().send_waitlist_confirmation("fan@example.com")

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["api-key"] == "test-key"
    body = req.body.decode() if isinstance(req.body, bytes) else req.body
    assert "fan@example.com" in body
    assert "hello@example.com" in body
    assert "waitlist" in body.lower()
