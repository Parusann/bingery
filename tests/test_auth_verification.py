"""Tests for the email-verification sign-up flow (pending_signup + endpoints)."""
from datetime import datetime, timedelta

import pytest

from models import db, PendingSignup, User


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
