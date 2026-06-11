"""Tests for the email-verification sign-up flow (pending_signup + endpoints)."""
from datetime import datetime, timedelta

import pytest

from models import db, PendingSignup, User


REGISTER_BODY = {
    "username": "newbie",
    "email": "new@example.com",
    "password": "password123",
}


def _register(client, **overrides):
    return client.post("/api/auth/register", json={**REGISTER_BODY, **overrides})


def test_pending_signup_model_defaults(app):
    row = PendingSignup(
        email="new@example.com",
        username="newbie",
        password_hash="x" * 60,
        code_hash="y" * 60,
        code_expires_at=datetime(2026, 1, 1, 0, 10),
        last_sent_at=datetime(2026, 1, 1, 0, 0),
        created_at=datetime(2026, 1, 1, 0, 0),
    )
    db.session.add(row)
    db.session.commit()

    fetched = db.session.query(PendingSignup).filter_by(email="new@example.com").one()
    assert fetched.attempts_remaining == 5
    assert fetched.resend_count == 0
    assert fetched.display_name is None


def test_register_creates_pending_not_user(client, sent_codes):
    r = _register(client)
    assert r.status_code == 202
    body = r.get_json()
    assert body == {"verification_required": True, "email": "new@example.com"}

    assert db.session.query(User).filter_by(email="new@example.com").first() is None
    pending = db.session.query(PendingSignup).filter_by(email="new@example.com").one()
    assert pending.username == "newbie"
    assert pending.attempts_remaining == 5

    assert len(sent_codes) == 1
    to_email, code = sent_codes[0]
    assert to_email == "new@example.com"
    assert len(code) == 6 and code.isdigit()
    # The code is stored hashed, never in plaintext.
    assert code not in pending.code_hash


def test_register_validation_errors_unchanged(client, sent_codes):
    r = client.post("/api/auth/register", json={"username": "ab"})
    assert r.status_code == 400
    assert isinstance(r.get_json()["error"], list)
    assert sent_codes == []


def test_register_verified_email_conflicts(client, sent_codes, auth_headers):
    # auth_headers creates a real user tester@example.com
    r = _register(client, email="tester@example.com", username="someoneelse")
    assert r.status_code == 409
    assert r.get_json() == {"error": "Email already registered."}


def test_register_taken_username_conflicts(client, sent_codes, auth_headers):
    r = _register(client, username="tester")
    assert r.status_code == 409
    assert r.get_json() == {"error": "Username already taken."}


def test_reregister_overwrites_pending(client, sent_codes):
    _register(client)
    r = _register(client, username="newname", password="otherpass1")
    assert r.status_code == 202

    rows = db.session.query(PendingSignup).filter_by(email="new@example.com").all()
    assert len(rows) == 1
    assert rows[0].username == "newname"
    assert len(sent_codes) == 2
    assert sent_codes[0][1] != rows[0].code_hash  # plaintext never stored


def test_register_email_failure_returns_503(client, monkeypatch):
    from utils.email_provider import EmailSendError

    class _Boom:
        def send_verification_code(self, to_email, code):
            raise EmailSendError("brevo down")

    monkeypatch.setattr("routes.auth.get_email_provider", lambda: _Boom())
    r = _register(client)
    assert r.status_code == 503
    assert "verification email" in r.get_json()["error"]
    # Pending row is kept so a retry can resend.
    assert db.session.query(PendingSignup).filter_by(email="new@example.com").count() == 1


def test_register_purges_stale_pendings(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client, email="old@example.com", username="oldtimer")

    real_now = auth_module._utcnow()
    monkeypatch.setattr(
        auth_module, "_utcnow", lambda: real_now + timedelta(hours=25)
    )
    _register(client)  # new@example.com — triggers the lazy purge

    assert db.session.query(PendingSignup).filter_by(email="old@example.com").count() == 0
    assert db.session.query(PendingSignup).filter_by(email="new@example.com").count() == 1
