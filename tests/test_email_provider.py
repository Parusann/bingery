"""Tests for utils/email_provider.py — console + Brevo providers and factory."""
import logging

import pytest
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
def test_brevo_network_error_raises(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", "test-key")
    monkeypatch.setenv("EMAIL_FROM", "codes@example.com")
    responses.add(
        responses.POST,
        "https://api.brevo.com/v3/smtp/email",
        body=ConnectionError("boom"),
    )
    with pytest.raises(EmailSendError):
        BrevoEmailProvider().send_verification_code("someone@example.com", "654321")
