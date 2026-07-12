"""Per-person invite-code gating on POST /api/auth/register.

The gate: registration requires the one-time code minted when the owner
approved that email's waitlist entry, and the code is consumed when the
account is created at verify. SIGNUP_OPEN=1 (set in conftest so unrelated
suites register freely) bypasses the gate; these tests turn it back on.
"""
import pytest

from models import db, Waitlist


@pytest.fixture
def gated(monkeypatch):
    """Re-enable the invite gate (conftest sets SIGNUP_OPEN=1 globally)."""
    monkeypatch.delenv("SIGNUP_OPEN", raising=False)


def _approve(email, code):
    entry = Waitlist(email=email, status="approved", invite_code=code)
    db.session.add(entry)
    db.session.commit()
    return entry


def _register(client, email, code=None, username="gateduser"):
    body = {"username": username, "email": email, "password": "password123"}
    if code is not None:
        body["invite_code"] = code
    return client.post("/api/auth/register", json=body)


def test_register_open_with_signup_open(client, sent_codes):
    # conftest sets SIGNUP_OPEN=1: no waitlist entry or code needed.
    r = _register(client, "open@example.com", username="openuser")
    assert r.status_code == 202, r.get_json()


def test_register_blocked_without_waitlist_entry(client, sent_codes, gated):
    r = _register(client, "nobody@example.com")
    assert r.status_code == 403
    assert "waitlist" in r.get_json()["error"].lower()
    assert sent_codes == []  # no verification email on a blocked signup


def test_register_blocked_while_entry_still_pending(client, sent_codes, gated):
    db.session.add(Waitlist(email="pending@example.com"))
    db.session.commit()
    r = _register(client, "pending@example.com", code="anything")
    assert r.status_code == 403
    assert sent_codes == []


def test_register_blocked_with_wrong_code(client, sent_codes, gated):
    _approve("gated@example.com", "right-code-123")
    r = _register(client, "gated@example.com", code="wrong-code")
    assert r.status_code == 403
    assert "match" in r.get_json()["error"].lower()
    assert sent_codes == []


def test_register_blocked_with_missing_code(client, sent_codes, gated):
    _approve("gated@example.com", "right-code-123")
    r = _register(client, "gated@example.com")
    assert r.status_code == 403
    assert sent_codes == []


def test_code_is_bound_to_its_email(client, sent_codes, gated):
    # A valid code stolen from someone else's invite must not work with
    # any other email address.
    _approve("victim@example.com", "victims-code-123")
    r = _register(client, "attacker@example.com", code="victims-code-123")
    assert r.status_code == 403
    assert sent_codes == []


def test_register_allowed_with_correct_code(client, sent_codes, gated):
    _approve("gated@example.com", "right-code-123")
    r = _register(client, "gated@example.com", code="right-code-123")
    assert r.status_code == 202, r.get_json()
    assert len(sent_codes) == 1  # verification email sent on success


def test_code_consumed_at_verify_and_rejected_after(client, sent_codes, gated):
    _approve("gated@example.com", "right-code-123")
    r = _register(client, "gated@example.com", code="right-code-123")
    assert r.status_code == 202, r.get_json()

    # Complete signup with the emailed verification code.
    _, verification_code = sent_codes[-1]
    r = client.post(
        "/api/auth/verify",
        json={"email": "gated@example.com", "code": verification_code},
    )
    assert r.status_code == 201, r.get_json()

    # The account's existence consumed the invite code.
    entry = db.session.query(Waitlist).filter_by(email="gated@example.com").one()
    assert entry.status == "registered"
    assert entry.code_used_at is not None

    # The same code can never mint another account.
    r = _register(client, "gated@example.com", code="right-code-123", username="again")
    assert r.status_code == 403
    assert "used" in r.get_json()["error"].lower()


def test_code_not_consumed_by_register_alone(client, sent_codes, gated):
    # Register without verify (e.g. abandoned or expired verification):
    # the code must still work for a fresh registration attempt.
    _approve("gated@example.com", "right-code-123")
    r = _register(client, "gated@example.com", code="right-code-123")
    assert r.status_code == 202

    entry = db.session.query(Waitlist).filter_by(email="gated@example.com").one()
    assert entry.status == "approved"
    assert entry.code_used_at is None
