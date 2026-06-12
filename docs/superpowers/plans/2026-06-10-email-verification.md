# Email Verification at Sign-Up — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registering emails a 6-digit code; the account (and its JWT) is only created when the code is verified.

**Architecture:** Verify-before-create — `POST /api/auth/register` writes a `pending_signup` row and sends a code; new `POST /api/auth/verify` creates the real `User` and returns the standard `{token, user}`; new `POST /api/auth/resend` re-issues codes. Email goes through a new `utils/email_provider.py` (`EMAIL_PROVIDER=console|brevo`) mirroring `utils/ai_provider.py`. No `user`-table change, no migration — `db.create_all()` creates the new table.

**Tech Stack:** Flask 3 / SQLAlchemy / Flask-Bcrypt / Flask-JWT-Extended; `requests` for Brevo (no new deps); pytest + `responses`; React 18 + TS + zustand on the frontend.

**Spec:** `docs/superpowers/specs/2026-06-10-email-verification-design.md`

**Branch:** all work on `feat/email-verification` (PR to `main` at the end — repo convention is merge-commit PRs for features).

**Run commands from the repo root** (`C:\Users\parus\Downloads\bingery-update`). Python tests: `python -m pytest …`. TypeScript check: `& 'frontend\node_modules\.bin\tsc.cmd' -b frontend`.

---

## File structure

| File | Action | Responsibility |
| --- | --- | --- |
| `utils/email_provider.py` | Create | `EmailSendError`, `ConsoleEmailProvider`, `BrevoEmailProvider`, `get_email_provider()` factory |
| `tests/test_email_provider.py` | Create | Provider unit tests (console logging, Brevo HTTP via `responses`, factory selection) |
| `config.py` | Modify | `EMAIL_PROVIDER` / `BREVO_API_KEY` / `EMAIL_FROM` + production boot guard |
| `models.py` | Modify | New `PendingSignup` model |
| `routes/auth.py` | Modify | Rewritten `register`, new `verify` + `resend`, `_utcnow()` clock helper, code helpers |
| `tests/conftest.py` | Modify | `sent_codes` fixture (records `(email, code)` instead of sending) |
| `tests/test_auth_verification.py` | Create | Full flow tests: register/verify/resend, expiry, attempts, purge |
| `tests/test_auth.py` | Modify | Update the 5 register-dependent tests to the two-step contract |
| `.env.example` | Modify | Document the three new env vars |
| `frontend/src/types/api.ts` | Modify | `RegisterPendingResponse` type |
| `frontend/src/lib/api.ts` | Modify | `register` return type, `verifyEmail`, `resendCode` |
| `frontend/src/stores/auth.ts` | Modify | `signUp` no longer authenticates; new `verifyEmail` / `resendCode` actions |
| `frontend/src/features/auth/AuthForm.tsx` | Modify | `step: "form" | "verify"` machine, code input, resend countdown, back link |

Frontend has no unit-test precedent (vitest deps exist but zero test files) — frontend tasks are verified with `tsc -b` plus a scripted manual smoke using the console provider.

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b feat/email-verification
```

---

### Task 1: Email provider module

**Files:**
- Create: `utils/email_provider.py`
- Test: `tests/test_email_provider.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_email_provider.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_email_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.email_provider'`

- [ ] **Step 3: Implement the provider module**

Create `utils/email_provider.py`:

```python
"""Email providers for verification codes.

Mirrors utils/ai_provider.py: a small factory keyed on an env var, with a
console provider for dev/tests and Brevo (https://brevo.com) for production.
Brevo is called over plain HTTP via `requests` — no extra dependency.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"


class EmailSendError(RuntimeError):
    """Raised when a verification email could not be sent.

    The register route catches this and returns a 503 so the user can
    simply retry — the pending signup row is kept.
    """


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
                "This code expires in 10 minutes. If you didn't create a "
                "Bingery account, you can ignore this email."
            ),
            "htmlContent": (
                "<div style=\"font-family:Arial,sans-serif;max-width:420px;"
                "margin:0 auto;padding:24px\">"
                "<h2 style=\"margin:0 0 12px\">Your Bingery verification code</h2>"
                f"<p style=\"font-size:32px;font-weight:bold;font-family:monospace;"
                f"letter-spacing:6px;margin:16px 0\">{code}</p>"
                "<p style=\"color:#555\">This code expires in 10 minutes. "
                "If you didn't create a Bingery account, you can ignore this "
                "email.</p></div>"
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
            raise EmailSendError(f"Brevo returned {resp.status_code}")


def get_email_provider():
    """Return an email provider selected by the `EMAIL_PROVIDER` env var."""
    name = (os.getenv("EMAIL_PROVIDER") or "console").strip().lower()
    if name == "console":
        return ConsoleEmailProvider()
    if name == "brevo":
        return BrevoEmailProvider()
    raise ValueError(
        f"Unknown EMAIL_PROVIDER: {name!r}. Expected 'console' or 'brevo'."
    )
```

Note: `responses` intercepts `ConnectionError` set as `body=` and re-raises it as
`requests.exceptions.ConnectionError`, which is a `RequestException` — the network
test passes through the same `except` branch as real outages.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_email_provider.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add utils/email_provider.py tests/test_email_provider.py
git commit -m "feat(auth): add email provider module (console + Brevo)"
```

---

### Task 2: Config vars + production boot guard

**Files:**
- Modify: `config.py` (add inside `class Config`, and extend the existing production-guard block)
- Modify: `.env.example`

The existing guard block runs at class-definition time and exits via `raise SystemExit(2)`. The email guard joins the same `problems` list. (The guard block has no existing tests — importing config is cached module state, so this stays consistent with the repo and is verified manually in Task 9's rollout.)

- [ ] **Step 1: Add the config values**

In `config.py`, inside `class Config`, directly after the `ANTHROPIC_API_KEY` line:

```python
    # Email verification (sign-up codes). 'console' logs the code (dev);
    # 'brevo' sends via the Brevo HTTP API (production).
    EMAIL_PROVIDER = (os.environ.get("EMAIL_PROVIDER") or "console").strip().lower()
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
```

- [ ] **Step 2: Extend the production guard**

In the same file, inside the `if _is_production():` block, after the `CORS_ORIGINS` check and before `if problems:`:

```python
        if EMAIL_PROVIDER != "brevo":
            problems.append(
                "EMAIL_PROVIDER must be 'brevo' in production (console would "
                "log verification codes instead of emailing them)"
            )
        elif not BREVO_API_KEY or not EMAIL_FROM:
            problems.append(
                "BREVO_API_KEY and EMAIL_FROM must be set when EMAIL_PROVIDER=brevo"
            )
```

- [ ] **Step 3: Document in `.env.example`**

Append after the `ANIMESCHEDULE_API_KEY` block:

```
# ── Email verification (sign-up codes) ────────────────────────────────────
# 'console' (default) logs the 6-digit code to the server log — for local
# dev and tests. Production requires 'brevo': create a free account at
# https://www.brevo.com, verify a sender address, and create an API key.
EMAIL_PROVIDER=console
BREVO_API_KEY=
EMAIL_FROM=
```

- [ ] **Step 4: Sanity-run the suite (config import still clean)**

Run: `python -m pytest tests/test_email_provider.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add config.py .env.example
git commit -m "feat(auth): config + production guard for email provider"
```

---

### Task 3: PendingSignup model

**Files:**
- Modify: `models.py` (add the class directly after the `User` class)
- Test: `tests/test_auth_verification.py` (new file, first test)

- [ ] **Step 1: Write the failing test**

Create `tests/test_auth_verification.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth_verification.py -v`
Expected: FAIL — `ImportError: cannot import name 'PendingSignup' from 'models'`

- [ ] **Step 3: Add the model**

In `models.py`, directly after the `User` class (match the existing declarative style):

```python
class PendingSignup(db.Model):
    """A sign-up awaiting email verification. Becomes a User when the
    6-digit code is verified; never serialized to clients.

    All datetimes are naive UTC (SQLite returns naive values), set
    explicitly by routes/auth.py rather than via column defaults so the
    route's monkeypatchable clock is the single time source.
    """

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(80), nullable=True, default=None)
    code_hash = db.Column(db.String(128), nullable=False)
    code_expires_at = db.Column(db.DateTime, nullable=False)
    attempts_remaining = db.Column(db.Integer, nullable=False, default=5)
    resend_count = db.Column(db.Integer, nullable=False, default=0)
    last_sent_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_auth_verification.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_auth_verification.py
git commit -m "feat(auth): PendingSignup model"
```

---

### Task 4: `sent_codes` fixture + register → 202 pending flow

**Files:**
- Modify: `tests/conftest.py` (append fixture)
- Modify: `tests/test_auth_verification.py` (add register tests)
- Modify: `routes/auth.py` (imports, helpers, rewritten `register`)

- [ ] **Step 1: Add the `sent_codes` fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def sent_codes(monkeypatch):
    """Capture (to_email, code) instead of sending real email.

    routes/auth.py imports get_email_provider at module level, so patch the
    name in that namespace.
    """
    sent: list[tuple[str, str]] = []

    class _Recorder:
        def send_verification_code(self, to_email, code):
            sent.append((to_email, code))

    monkeypatch.setattr("routes.auth.get_email_provider", lambda: _Recorder())
    return sent
```

- [ ] **Step 2: Write the failing register tests**

Append to `tests/test_auth_verification.py`:

```python
REGISTER_BODY = {
    "username": "newbie",
    "email": "new@example.com",
    "password": "password123",
}


def _register(client, **overrides):
    return client.post("/api/auth/register", json={**REGISTER_BODY, **overrides})


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_auth_verification.py -v`
Expected: the new tests FAIL (register still returns 201 with a token; `_utcnow` missing)

- [ ] **Step 4: Rewrite `register` in `routes/auth.py`**

Replace the import block and the `register` function. New top-of-file (imports + helpers):

```python
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from models import db, PendingSignup, User
from utils.email_provider import EmailSendError, get_email_provider

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
bcrypt = Bcrypt()

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_RESENDS = 5
PENDING_MAX_AGE = timedelta(hours=24)


def _utcnow() -> datetime:
    """Naive UTC now. SQLite hands back naive datetimes, so all
    pending-signup time math stays naive-to-naive. Module-level so tests
    can monkeypatch the clock."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"
```

Replace the body of `register()` (validation and the two 409 checks stay byte-identical; everything after them changes):

```python
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    # ── Validate ──────────────────────────────────────────────────────────
    errors = []
    if not data.get("username") or len(data["username"].strip()) < 3:
        errors.append("Username must be at least 3 characters.")
    if not data.get("email") or "@" not in data.get("email", ""):
        errors.append("A valid email is required.")
    if not data.get("password") or len(data["password"]) < 6:
        errors.append("Password must be at least 6 characters.")
    if errors:
        return jsonify({"error": errors}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()

    if db.session.query(User).filter_by(username=username).first():
        return jsonify({"error": "Username already taken."}), 409
    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    now = _utcnow()

    # ── Lazy purge of abandoned signups ──────────────────────────────────
    db.session.query(PendingSignup).filter(
        PendingSignup.created_at < now - PENDING_MAX_AGE
    ).delete()

    display_name_raw = data.get("display_name")
    display_name = (
        display_name_raw.strip()[:80] if isinstance(display_name_raw, str) and display_name_raw.strip()
        else None
    )

    # ── Upsert the pending signup (re-register overwrites: the previous
    #    holder never proved ownership of this email) ──────────────────────
    code = _generate_code()
    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    if pending is None:
        pending = PendingSignup(email=email, created_at=now)
        db.session.add(pending)
    else:
        pending.created_at = now
    pending.username = username
    pending.password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    pending.display_name = display_name
    pending.code_hash = bcrypt.generate_password_hash(code).decode("utf-8")
    pending.code_expires_at = now + CODE_TTL
    pending.attempts_remaining = 5
    pending.resend_count = 0
    pending.last_sent_at = now

    try:
        get_email_provider().send_verification_code(email, code)
    except EmailSendError:
        db.session.commit()  # keep the pending row; the user can retry
        return (
            jsonify({"error": "Couldn't send the verification email. Please try again."}),
            503,
        )

    db.session.commit()
    return jsonify({"verification_required": True, "email": email}), 202
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/test_auth_verification.py -v`
Expected: all pass (model test + 7 register tests)

- [ ] **Step 6: Update `tests/test_auth.py` to the two-step contract**

The five existing tests register and expect `201` + immediate persistence/token. Add a helper at the top of the file (after the docstring) and rewrite the tests to go through verify:

```python
"""Tests for /api/auth endpoints, focused on the display_name field."""


def _register_verified(client, sent_codes, payload):
    """Two-step sign-up: register (202) then verify with the emailed code.
    Returns the verify response (201 {token, user})."""
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 202, r.get_json()
    _, code = sent_codes[-1]
    rv = client.post(
        "/api/auth/verify",
        json={"email": payload["email"], "code": code},
    )
    assert rv.status_code == 201, rv.get_json()
    return rv
```

Then each test changes from `r = client.post("/api/auth/register", json={…}); assert r.status_code == 201` to:

```python
def test_register_persists_display_name(client, sent_codes):
    """display_name is optional but, when provided, persists and echoes back."""
    r = _register_verified(client, sent_codes, {
        "username": "dn_user",
        "email": "dn@example.com",
        "password": "password123",
        "display_name": "Display Name",
    })
    body = r.get_json()
    assert body["user"]["display_name"] == "Display Name"
```

Apply the same mechanical change to `test_register_without_display_name_defaults_to_null`, `test_register_strips_and_truncates_display_name`, `test_register_empty_display_name_treated_as_unset` (each: add `sent_codes` parameter, call `_register_verified(client, sent_codes, {...same payload...})`, drop the old `assert r.status_code == 201` line, keep the body assertions). In `test_update_profile_can_change_display_name`, replace the register call with `r = _register_verified(client, sent_codes, {...})` and keep `token = r.get_json()["token"]` — the verify response carries the token now.

Note: these will stay RED until Task 5 implements `/verify` — that's expected; run only `tests/test_auth_verification.py` for now.

- [ ] **Step 7: Commit**

```bash
git add routes/auth.py tests/conftest.py tests/test_auth_verification.py tests/test_auth.py
git commit -m "feat(auth): register now creates a pending signup and emails a 6-digit code"
```

---

### Task 5: `POST /api/auth/verify`

**Files:**
- Modify: `routes/auth.py` (new endpoint after `register`)
- Modify: `tests/test_auth_verification.py` (verify tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_auth_verification.py`:

```python
def _code_for(sent_codes, email="new@example.com"):
    return [c for (to, c) in sent_codes if to == email][-1]


def _verify(client, code, email="new@example.com"):
    return client.post("/api/auth/verify", json={"email": email, "code": code})


UNIFORM = {"error": "Invalid or expired code."}


def test_verify_happy_path_creates_user_and_token(client, sent_codes):
    _register(client)
    r = _verify(client, _code_for(sent_codes))
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["username"] == "newbie"
    assert body["user"]["email"] == "new@example.com"

    # Pending row consumed; real user exists; token works.
    assert db.session.query(PendingSignup).count() == 0
    assert db.session.query(User).filter_by(email="new@example.com").count() == 1
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200

    # And the password from registration works for login.
    login = client.post(
        "/api/auth/login",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert login.status_code == 200


def test_verify_wrong_code_decrements_attempts(client, sent_codes):
    _register(client)
    right = _code_for(sent_codes)
    wrong = "000000" if right != "000000" else "000001"

    r = _verify(client, wrong)
    assert r.status_code == 400
    assert r.get_json() == UNIFORM
    pending = db.session.query(PendingSignup).one()
    assert pending.attempts_remaining == 4

    # The right code still works while attempts remain.
    assert _verify(client, right).status_code == 201


def test_verify_attempts_exhaustion_blocks_even_correct_code(client, sent_codes):
    _register(client)
    right = _code_for(sent_codes)
    wrong = "000000" if right != "000000" else "000001"

    for _ in range(5):
        assert _verify(client, wrong).status_code == 400
    # Correct code is now dead too — must resend.
    r = _verify(client, right)
    assert r.status_code == 400
    assert r.get_json() == UNIFORM
    assert db.session.query(User).count() == 0


def test_verify_expired_code(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)
    right = _code_for(sent_codes)
    real_now = auth_module._utcnow()
    monkeypatch.setattr(auth_module, "_utcnow", lambda: real_now + timedelta(minutes=11))

    r = _verify(client, right)
    assert r.status_code == 400
    assert r.get_json() == UNIFORM


def test_verify_unknown_email_uniform(client):
    r = _verify(client, "123456", email="nobody@example.com")
    assert r.status_code == 400
    assert r.get_json() == UNIFORM


def test_verify_username_race_returns_409(client, sent_codes, app):
    """Someone claims the username between register and verify."""
    from flask_bcrypt import Bcrypt

    _register(client)
    other = User(
        username="newbie",
        email="other@example.com",
        password_hash=Bcrypt(app).generate_password_hash("pw123456").decode("utf-8"),
    )
    db.session.add(other)
    db.session.commit()

    r = _verify(client, _code_for(sent_codes))
    assert r.status_code == 409
    assert r.get_json() == {"error": "Username already taken."}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_auth_verification.py -v`
Expected: new verify tests FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Implement the endpoint**

Add to `routes/auth.py`, directly after `register`:

```python
@auth_bp.route("/verify", methods=["POST"])
def verify():
    """Exchange a pending signup + correct code for a real account + JWT.

    Every failure mode (unknown email, expired, attempts exhausted, wrong
    code) returns the same body so nothing is leaked about which it was.
    """
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    uniform = jsonify({"error": "Invalid or expired code."}), 400

    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    if not pending or not code:
        return uniform

    now = _utcnow()
    if now > pending.code_expires_at or pending.attempts_remaining <= 0:
        return uniform

    if not bcrypt.check_password_hash(pending.code_hash, code):
        pending.attempts_remaining -= 1
        db.session.commit()
        return uniform

    # ── Race guard: the username/email may have been claimed since ───────
    if db.session.query(User).filter_by(username=pending.username).first():
        return jsonify({"error": "Username already taken."}), 409
    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    user = User(
        username=pending.username,
        email=email,
        password_hash=pending.password_hash,
        display_name=pending.display_name,
    )
    db.session.add(user)
    db.session.delete(pending)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201
```

- [ ] **Step 4: Run the file's tests, then the whole suite**

Run: `python -m pytest tests/test_auth_verification.py tests/test_auth.py -v`
Expected: all pass — including the Task 4 rewrites of `test_auth.py`, now green.

Run: `python -m pytest -q`
Expected: everything passes (301 pre-existing + the new ones; no other suite touches register).

- [ ] **Step 5: Commit**

```bash
git add routes/auth.py tests/test_auth_verification.py
git commit -m "feat(auth): verify endpoint creates the account and issues the JWT"
```

---

### Task 6: `POST /api/auth/resend`

**Files:**
- Modify: `routes/auth.py` (new endpoint after `verify`)
- Modify: `tests/test_auth_verification.py` (resend tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_auth_verification.py`:

```python
def _resend(client, email="new@example.com"):
    return client.post("/api/auth/resend", json={"email": email})


def test_resend_within_cooldown_is_silent_noop(client, sent_codes):
    _register(client)
    r = _resend(client)
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
    assert len(sent_codes) == 1  # nothing new sent


def test_resend_after_cooldown_issues_new_code(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)
    old_code = _code_for(sent_codes)
    # burn two attempts so we can see the reset
    wrong = "000000" if old_code != "000000" else "000001"
    _verify(client, wrong)

    real_now = auth_module._utcnow()
    monkeypatch.setattr(auth_module, "_utcnow", lambda: real_now + timedelta(seconds=61))

    assert _resend(client).status_code == 200
    assert len(sent_codes) == 2
    new_code = _code_for(sent_codes)

    pending = db.session.query(PendingSignup).one()
    assert pending.attempts_remaining == 5
    assert pending.resend_count == 1

    # Old code dead, new code works.
    assert _verify(client, old_code).status_code == 400 or old_code == new_code
    assert _verify(client, new_code).status_code == 201


def test_resend_cap_at_five(client, sent_codes, monkeypatch):
    import routes.auth as auth_module

    _register(client)
    real_now = auth_module._utcnow()
    for i in range(1, 8):
        monkeypatch.setattr(
            auth_module, "_utcnow",
            lambda offset=i: real_now + timedelta(seconds=61 * offset),
        )
        assert _resend(client).status_code == 200

    pending = db.session.query(PendingSignup).one()
    assert pending.resend_count == 5
    assert len(sent_codes) == 1 + 5  # initial + 5 resends, then capped


def test_resend_unknown_email_uniform_200(client, sent_codes):
    r = _resend(client, email="nobody@example.com")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
    assert sent_codes == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_auth_verification.py -k resend -v`
Expected: FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Implement the endpoint**

Add to `routes/auth.py`, directly after `verify`:

```python
@auth_bp.route("/resend", methods=["POST"])
def resend():
    """Re-issue a verification code. Constant response regardless of
    whether the email has a pending signup (anti-enumeration); cooldown
    and the resend cap are silent no-ops."""
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    ok = jsonify({"ok": True}), 200

    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    if not pending:
        return ok

    now = _utcnow()
    if now - pending.last_sent_at < RESEND_COOLDOWN or pending.resend_count >= MAX_RESENDS:
        return ok

    code = _generate_code()
    pending.code_hash = bcrypt.generate_password_hash(code).decode("utf-8")
    pending.code_expires_at = now + CODE_TTL
    pending.attempts_remaining = 5
    pending.resend_count += 1
    pending.last_sent_at = now

    try:
        get_email_provider().send_verification_code(email, code)
    except EmailSendError:
        db.session.rollback()
        return ok  # constant response even on send failure

    db.session.commit()
    return ok
```

- [ ] **Step 4: Run the full backend suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add routes/auth.py tests/test_auth_verification.py
git commit -m "feat(auth): resend endpoint with cooldown, cap, and uniform response"
```

---

### Task 7: Frontend API client, types, and store

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/stores/auth.ts`

- [ ] **Step 1: Types**

In `frontend/src/types/api.ts`, directly after the `AuthResponse` interface:

```ts
export interface RegisterPendingResponse {
  verification_required: true;
  email: string;
}
```

- [ ] **Step 2: API client**

In `frontend/src/lib/api.ts`: add `RegisterPendingResponse` to the existing `import type { … } from "@/types/api"` list, then change `register` and add two methods directly after it:

```ts
  register: (body: { email: string; password: string; username: string; display_name?: string }) =>
    request<RegisterPendingResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  verifyEmail: (body: { email: string; code: string }) =>
    request<AuthResponse>("/auth/verify", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  resendCode: (body: { email: string }) =>
    request<{ ok: true }>("/auth/resend", {
      method: "POST",
      body: JSON.stringify(body),
    }),
```

- [ ] **Step 3: Store**

In `frontend/src/stores/auth.ts`:

Replace the `signUp` entry in the `AuthState` interface and add two actions:

```ts
  /** Starts sign-up: sends the verification code. Does NOT authenticate. */
  signUp: (body: { email: string; password: string; username: string; display_name?: string }) => Promise<void>;
  /** Completes sign-up: exchanges email+code for a token and signs in. */
  verifyEmail: (body: { email: string; code: string }) => Promise<void>;
  resendCode: (body: { email: string }) => Promise<void>;
```

Replace the `signUp` implementation and add the new actions after it:

```ts
  async signUp(body) {
    set({ status: "loading", error: null });
    try {
      await api.register(body);
      // No token yet — the verify step completes authentication.
      set({ status: "idle" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  async verifyEmail(body) {
    set({ status: "loading", error: null });
    try {
      const res = await api.verifyEmail(body);
      api.setToken(res.token);
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  async resendCode(body) {
    try {
      await api.resendCode(body);
    } catch (e) {
      set({ error: (e as Error).message });
      throw e;
    }
  },
```

- [ ] **Step 4: Type-check**

Run: `& 'frontend\node_modules\.bin\tsc.cmd' -b frontend`
Expected: exit 0. (AuthForm still compiles: it awaits `signUp` and ignores the return value.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/stores/auth.ts
git commit -m "feat(auth): frontend api + store for the verify step"
```

---

### Task 8: AuthForm verify step

**Files:**
- Modify: `frontend/src/features/auth/AuthForm.tsx` (full replacement below)

- [ ] **Step 1: Replace `AuthForm.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Input } from "@/design/Input";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";

type Mode = "login" | "register";
type Step = "form" | "verify";

const RESEND_SECONDS = 60;

export function AuthForm({ onSuccess }: { onSuccess?: () => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("form");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(RESEND_SECONDS);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const signIn = useAuth((s) => s.signIn);
  const signUp = useAuth((s) => s.signUp);
  const verifyEmail = useAuth((s) => s.verifyEmail);
  const resendCode = useAuth((s) => s.resendCode);

  // Resend countdown, ticking only on the verify step.
  useEffect(() => {
    if (step !== "verify" || resendIn <= 0) return;
    const t = setInterval(() => setResendIn((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [step, resendIn]);

  const submit = async () => {
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await signIn({ email, password });
        onSuccess?.();
      } else if (step === "form") {
        await signUp({
          email,
          password,
          username,
          display_name: displayName.trim() || undefined,
        });
        setCode("");
        setResendIn(RESEND_SECONDS);
        setResent(false);
        setStep("verify");
      } else {
        await verifyEmail({ email: email.trim().toLowerCase(), code });
        onSuccess?.();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setError(null);
    try {
      await resendCode({ email: email.trim().toLowerCase() });
      setResendIn(RESEND_SECONDS);
      setResent(true);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (step === "verify") {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex flex-col gap-4"
      >
        <div>
          <h2 className="font-display text-2xl mb-1">Check your email</h2>
          <p className="text-sm text-text-muted">
            We sent a 6-digit code to <span className="text-text">{email}</span>.
          </p>
        </div>
        <Input
          label="Verification code"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          autoComplete="one-time-code"
          className="text-center tracking-[0.4em] font-mono text-lg"
          required
        />
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        {resent && !error ? (
          <p className="text-sm text-text-muted">Code sent.</p>
        ) : null}
        <Button type="submit" loading={loading} disabled={code.length !== 6}>
          Verify
        </Button>
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={resend}
            disabled={resendIn > 0}
            className="text-text-muted hover:text-text disabled:opacity-50 disabled:hover:text-text-muted"
          >
            {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
          </button>
          <button
            type="button"
            onClick={() => {
              setStep("form");
              setError(null);
            }}
            className="text-text-muted hover:text-text"
          >
            Wrong email? Go back
          </button>
        </div>
      </form>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex flex-col gap-4"
    >
      <div className="flex gap-2 text-sm">
        <button
          type="button"
          onClick={() => setMode("login")}
          className={
            "px-3 py-1.5 rounded-md " +
            (mode === "login"
              ? "bg-white/[0.08] text-text"
              : "text-text-muted hover:text-text")
          }
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => setMode("register")}
          className={
            "px-3 py-1.5 rounded-md " +
            (mode === "register"
              ? "bg-white/[0.08] text-text"
              : "text-text-muted hover:text-text")
          }
        >
          Sign up
        </button>
      </div>

      {mode === "register" ? (
        <>
          <Input
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <Input
            label="Display name (optional)"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="nickname"
          />
        </>
      ) : null}
      <Input
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
        required
      />
      <Input
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        required
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Button type="submit" loading={loading}>
        {mode === "login" ? "Sign in" : "Create account"}
      </Button>
    </form>
  );
}
```

Notes: the `Input` primitive spreads extra props onto the native `<input>` (it extends `InputHTMLAttributes`), so `inputMode`/`pattern`/`maxLength`/`className` pass through; its `className` lands on the inner input element.

- [ ] **Step 2: Type-check**

Run: `& 'frontend\node_modules\.bin\tsc.cmd' -b frontend`
Expected: exit 0

- [ ] **Step 3: Manual smoke (console provider)**

1. Terminal A: `python app.py` (dev backend, `EMAIL_PROVIDER` unset → console).
2. Terminal B: `cd frontend; npm run dev` → open http://localhost:5173/auth.
3. Sign up with a fresh email → form switches to "Check your email"; the code appears in Terminal A's log (`Verification code for …`).
4. Enter a wrong code → "Invalid or expired code." renders in red; correct code → lands signed-in on /discover.
5. "Resend code" disabled with countdown; after 60 s it re-sends (new log line). "Wrong email? Go back" returns to the filled form.
6. Sign in with the new account works; sign in with a pre-existing account untouched.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/auth/AuthForm.tsx
git commit -m "feat(auth): verification-code step in the sign-up form"
```

---

### Task 9: Final verification, PR, rollout

- [ ] **Step 1: Full guards**

```bash
python -m pytest -q                       # expect: 301 + ~19 new, all passing
```
```powershell
& 'frontend\node_modules\.bin\tsc.cmd' -b frontend   # expect: exit 0
```

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin feat/email-verification
gh pr create --base main --title "Email verification at sign-up (6-digit code)" --body "<summary per repo convention — no AI attribution>"
```

- [ ] **Step 3: Merge after review** (repo convention)

```bash
gh pr merge --merge --delete-branch
```

- [ ] **Step 4: Production rollout (one-time, manual)**

1. Brevo: create the free account, verify the sender address (dashboard → Senders, e.g. your Gmail), create an API key.
2. `fly secrets set EMAIL_PROVIDER=brevo BREVO_API_KEY=<key> EMAIL_FROM=<verified sender>` (machine restarts).
3. `fly deploy` — `db.create_all()` creates `pending_signup` on boot; no data migration.
4. Smoke on https://bingery.fly.dev: register with a real inbox → code arrives → verify → signed in on /discover; existing account still logs in; `curl https://bingery.fly.dev/api/health` → 200.

---

## Self-review notes

- Spec coverage: §5→Task 3, §6 register→Task 4, verify→Task 5, resend→Task 6, §7→Tasks 1–2, §9→Tasks 7–8, §10→Tasks 1/3–6 + manual smoke, §11→Task 9. Spec §10.8 (boot-guard test) is intentionally manual — import-time guards aren't unit-testable without subprocess machinery the repo doesn't use; noted in Task 2.
- Types consistent: `_utcnow`/`_generate_code`/`CODE_TTL`/`RESEND_COOLDOWN`/`MAX_RESENDS`/`PENDING_MAX_AGE` defined once in Task 4 and reused in Tasks 5–6; `RegisterPendingResponse` defined in Task 7 Step 1 before use in Step 2; `sent_codes` fixture defined in Task 4 before use in Tasks 4–6 and `test_auth.py`.
- The one cross-file hazard: Task 4 leaves `tests/test_auth.py` red until Task 5 lands — called out explicitly in both tasks.
