"""Owner-only waitlist admin endpoints, the approve→invite loop, the
owner-account seed CLI, and the legacy-table column migration."""
import pytest
from flask_jwt_extended import create_access_token

from models import db, User, Waitlist
from utils.email_provider import EmailSendError


@pytest.fixture
def owner_headers(app):
    """JWT headers for the solo-owner account (email == OWNER_EMAIL)."""
    from routes.auth import bcrypt

    owner = User(
        username="owner",
        email=app.config["OWNER_EMAIL"],
        password_hash=bcrypt.generate_password_hash("ownerpass").decode("utf-8"),
    )
    db.session.add(owner)
    db.session.commit()
    token = create_access_token(identity=str(owner.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def invites(monkeypatch):
    """Capture (to_email, code, signup_url) instead of sending invites.

    routes/waitlist.py imports get_email_provider at module level, so patch
    the name in that namespace (same approach as conftest's sent_codes).
    """
    sent: list[tuple[str, str, str]] = []

    class _Recorder:
        def send_waitlist_invite(self, to_email, code, signup_url):
            sent.append((to_email, code, signup_url))

    monkeypatch.setattr("routes.waitlist.get_email_provider", lambda: _Recorder())
    return sent


def _pending(email="fan@example.com"):
    entry = Waitlist(email=email)
    db.session.add(entry)
    db.session.commit()
    return entry


# ─── Authorization ───────────────────────────────────────────────────────────

def test_admin_list_requires_token(client):
    assert client.get("/api/waitlist/admin").status_code == 401


def test_admin_list_rejects_non_owner(client, auth_headers):
    headers, _user = auth_headers
    r = client.get("/api/waitlist/admin", headers=headers)
    assert r.status_code == 403


def test_admin_approve_requires_token(client):
    entry = _pending()
    assert client.post(f"/api/waitlist/admin/{entry.id}/approve").status_code == 401


def test_admin_approve_rejects_non_owner(client, auth_headers, invites):
    headers, _user = auth_headers
    entry = _pending()
    r = client.post(f"/api/waitlist/admin/{entry.id}/approve", headers=headers)
    assert r.status_code == 403
    assert invites == []
    assert db.session.get(Waitlist, entry.id).status == "pending"


# ─── Listing ─────────────────────────────────────────────────────────────────

def test_admin_list_returns_entries_newest_first(client, owner_headers):
    from datetime import datetime, timedelta, timezone

    older = Waitlist(
        email="older@example.com",
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    newer = Waitlist(email="newer@example.com")
    db.session.add_all([older, newer])
    db.session.commit()

    r = client.get("/api/waitlist/admin", headers=owner_headers)
    assert r.status_code == 200
    entries = r.get_json()["entries"]
    assert [e["email"] for e in entries] == ["newer@example.com", "older@example.com"]
    assert entries[0]["status"] == "pending"
    assert set(entries[0]) >= {
        "id", "email", "created_at", "status", "invite_code",
        "approved_at", "code_used_at",
    }


# ─── Approval ────────────────────────────────────────────────────────────────

def test_approve_mints_code_and_emails_invite(client, owner_headers, invites):
    entry = _pending()
    r = client.post(f"/api/waitlist/admin/{entry.id}/approve", headers=owner_headers)
    assert r.status_code == 200, r.get_json()

    body = r.get_json()["entry"]
    assert body["status"] == "approved"
    assert body["approved_at"] is not None
    code = body["invite_code"]
    assert code and len(code) >= 16  # token_urlsafe(16) → ~22 chars

    # Persisted, not just serialized.
    fresh = db.session.get(Waitlist, entry.id)
    assert fresh.status == "approved"
    assert fresh.invite_code == code

    # The person got the code and a signup link carrying it.
    assert len(invites) == 1
    to_email, sent_code, signup_url = invites[0]
    assert to_email == "fan@example.com"
    assert sent_code == code
    assert code in signup_url and "/auth?" in signup_url


def test_approve_unknown_entry_404(client, owner_headers, invites):
    r = client.post("/api/waitlist/admin/9999/approve", headers=owner_headers)
    assert r.status_code == 404
    assert invites == []


def test_approve_twice_conflicts(client, owner_headers, invites):
    entry = _pending()
    assert (
        client.post(f"/api/waitlist/admin/{entry.id}/approve", headers=owner_headers)
        .status_code == 200
    )
    r = client.post(f"/api/waitlist/admin/{entry.id}/approve", headers=owner_headers)
    assert r.status_code == 409
    assert len(invites) == 1  # no second invite email


def test_approve_email_failure_rolls_back(client, owner_headers, monkeypatch):
    class _Boom:
        def send_waitlist_invite(self, *args):
            raise EmailSendError("brevo down")

    monkeypatch.setattr("routes.waitlist.get_email_provider", lambda: _Boom())
    entry = _pending()
    r = client.post(f"/api/waitlist/admin/{entry.id}/approve", headers=owner_headers)
    assert r.status_code == 503

    # Nothing changed: still pending, no half-minted code, safe to retry.
    fresh = db.session.get(Waitlist, entry.id)
    assert fresh.status == "pending"
    assert fresh.invite_code is None
    assert fresh.approved_at is None


# ─── Owner flag on auth responses ────────────────────────────────────────────

def test_login_marks_owner(client, app, owner_headers):
    r = client.post(
        "/api/auth/login",
        json={"email": app.config["OWNER_EMAIL"], "password": "ownerpass"},
    )
    assert r.status_code == 200
    assert r.get_json()["user"]["is_owner"] is True


def test_login_marks_non_owner(client, auth_headers):
    r = client.post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "password"},
    )
    assert r.status_code == 200
    assert r.get_json()["user"]["is_owner"] is False


# ─── seed-owner CLI ──────────────────────────────────────────────────────────

def test_seed_owner_creates_login_capable_account(app, monkeypatch):
    from routes.auth import bcrypt

    monkeypatch.setenv("OWNER_INITIAL_PASSWORD", "s3cret-initial")
    result = app.test_cli_runner().invoke(args=["seed-owner"])
    assert "Seeded owner account" in result.output, result.output

    user = db.session.query(User).filter_by(email=app.config["OWNER_EMAIL"]).one()
    # Hashed with the same mechanism register/login use.
    assert bcrypt.check_password_hash(user.password_hash, "s3cret-initial")

    # Idempotent: a re-run never touches the existing account.
    result = app.test_cli_runner().invoke(args=["seed-owner"])
    assert "already exists" in result.output


def test_seed_owner_refuses_without_password(app, monkeypatch):
    monkeypatch.delenv("OWNER_INITIAL_PASSWORD", raising=False)
    result = app.test_cli_runner().invoke(args=["seed-owner"])
    assert result.exit_code != 0
    assert db.session.query(User).count() == 0


# ─── Legacy-table migration ──────────────────────────────────────────────────

def test_ensure_waitlist_columns_upgrades_legacy_table(app):
    from sqlalchemy import inspect, text
    from app import _ensure_waitlist_columns

    # Rebuild the waitlist table in its pre-approval shape, with one row
    # already on it (as in production).
    db.session.remove()
    with db.engine.begin() as conn:
        conn.execute(text("DROP TABLE waitlist"))
        conn.execute(text(
            "CREATE TABLE waitlist ("
            "id INTEGER PRIMARY KEY, "
            "email VARCHAR(120) NOT NULL UNIQUE, "
            "created_at DATETIME NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO waitlist (email, created_at) "
            "VALUES ('legacy@example.com', '2026-06-18 00:00:00')"
        ))

    _ensure_waitlist_columns()

    cols = {c["name"] for c in inspect(db.engine).get_columns("waitlist")}
    assert {"status", "invite_code", "approved_at", "code_used_at"} <= cols

    # Pre-existing rows come out as pending, and the ORM can read them.
    legacy = db.session.query(Waitlist).filter_by(email="legacy@example.com").one()
    assert legacy.status == "pending"
    assert legacy.invite_code is None

    # Re-running is a no-op (idempotence guards every deploy).
    _ensure_waitlist_columns()
