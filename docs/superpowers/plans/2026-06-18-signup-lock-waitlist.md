# Signup Lock + Waitlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the landing waitlist form real (persist + confirmation email) and lock account signup behind a single shared invite code.

**Architecture:** A new `Waitlist` model + public `POST /api/waitlist` endpoint that records the email and sends a confirmation via the existing email-provider factory (extended with `send_waitlist_confirmation`). Signup is gated in `routes/auth.py` `register()` by a `SIGNUP_INVITE_CODE` env var (active only when set; required by the prod boot guard). The hand-built `landing.html` form is wired to the endpoint, and the React `AuthForm` gains an invite-code field.

**Tech Stack:** Flask + SQLAlchemy (backend, pytest + the `responses` lib for HTTP mocking), React + TypeScript + Vite (frontend), Brevo HTTP API for prod email.

Spec: `docs/superpowers/specs/2026-06-18-signup-lock-waitlist-design.md`
Branch: `feat/signup-lock-waitlist`

**Project rule:** Commit messages must contain NO AI/Claude attribution (no `Co-Authored-By`, no "Generated with").

---

## File structure

- `utils/email_provider.py` — MODIFY: add `send_waitlist_confirmation` to the Protocol + both providers; refactor Brevo's HTTP POST into a shared `_send` helper (DRY).
- `tests/test_email_provider.py` — ADD two tests for the new method.
- `models.py` — ADD a `Waitlist` model.
- `routes/waitlist.py` — NEW blueprint with `POST /api/waitlist`.
- `app.py` — MODIFY: register the new blueprint.
- `tests/test_waitlist.py` — NEW endpoint tests.
- `config.py` — MODIFY: add `SIGNUP_INVITE_CODE` + a production boot-guard requirement.
- `routes/auth.py` — MODIFY: gate `register()` on `SIGNUP_INVITE_CODE` (read live from env).
- `tests/conftest.py` — MODIFY: scrub `SIGNUP_INVITE_CODE` so gating is off by default in tests.
- `tests/test_auth_gating.py` — NEW gating tests.
- `frontend/public/landing.html` — MODIFY: replace the fake submit handler with a real `fetch`.
- `frontend/src/lib/api.ts` — MODIFY: add `invite_code?` to the register body type.
- `frontend/src/stores/auth.ts` — MODIFY: add `invite_code?` to the `signUp` signature.
- `frontend/src/features/auth/AuthForm.tsx` — MODIFY: invite-code input + waitlist link.

---

## Task 1: Email provider — waitlist confirmation

**Files:**
- Modify: `utils/email_provider.py`
- Test: `tests/test_email_provider.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_email_provider.py` (it already imports `BrevoEmailProvider`, `ConsoleEmailProvider`, `EmailSendError`, `get_email_provider`, `logging`, `pytest`, `requests`, `responses`):

```python
def test_console_provider_logs_waitlist_confirmation(caplog):
    provider = ConsoleEmailProvider()
    with caplog.at_level(logging.INFO):
        provider.send_waitlist_confirmation("fan@example.com")
    assert "fan@example.com" in caplog.text


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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_email_provider.py -k waitlist -v`
Expected: FAIL — `AttributeError: ... has no attribute 'send_waitlist_confirmation'`.

- [ ] **Step 3: Implement**

In `utils/email_provider.py`, replace the block from the `@runtime_checkable` line through the end of `BrevoEmailProvider` (currently lines 32–87) with:

```python
@runtime_checkable
class EmailProvider(Protocol):
    """What the auth + waitlist routes need from a provider."""

    def send_verification_code(self, to_email: str, code: str) -> None: ...

    def send_waitlist_confirmation(self, to_email: str) -> None: ...


class ConsoleEmailProvider:
    """Dev/test provider: the 'email' is a log line."""

    def send_verification_code(self, to_email: str, code: str) -> None:
        logger.info("Verification code for %s: %s", to_email, code)

    def send_waitlist_confirmation(self, to_email: str) -> None:
        logger.info("Waitlist confirmation for %s", to_email)


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
```

This keeps `send_verification_code`'s payload byte-for-byte identical (so the existing Brevo tests pass) and adds the waitlist method via the shared `_send` helper.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_email_provider.py -v`
Expected: PASS (new waitlist tests + all existing provider tests).

- [ ] **Step 5: Commit**

```bash
git add utils/email_provider.py tests/test_email_provider.py
git commit -m "feat(email): add waitlist confirmation email to providers"
```

---

## Task 2: Waitlist model + endpoint

**Files:**
- Modify: `models.py`, `app.py`
- Create: `routes/waitlist.py`
- Test: `tests/test_waitlist.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_waitlist.py`:

```python
"""Tests for the public waitlist endpoint."""
import pytest

from models import db, Waitlist


@pytest.fixture
def sent_waitlist(monkeypatch):
    """Capture confirmation sends instead of emailing. The waitlist route
    imports get_email_provider at module level, so patch it there."""
    sent: list[str] = []

    class _Recorder:
        def send_waitlist_confirmation(self, to_email):
            sent.append(to_email)

    monkeypatch.setattr("routes.waitlist.get_email_provider", lambda: _Recorder())
    return sent


def test_join_waitlist_adds_and_sends(client, app, sent_waitlist):
    r = client.post("/api/waitlist", json={"email": "New@Example.com"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["status"] == "added"
    assert sent_waitlist == ["new@example.com"]  # normalized lowercase
    with app.app_context():
        assert (
            db.session.query(Waitlist).filter_by(email="new@example.com").count() == 1
        )


def test_join_waitlist_duplicate_reports_already(client, app, sent_waitlist):
    client.post("/api/waitlist", json={"email": "dupe@example.com"})
    sent_waitlist.clear()
    r = client.post("/api/waitlist", json={"email": "dupe@example.com"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "already"
    assert sent_waitlist == []  # no second email
    with app.app_context():
        assert (
            db.session.query(Waitlist).filter_by(email="dupe@example.com").count() == 1
        )


def test_join_waitlist_rejects_invalid_email(client, sent_waitlist):
    r = client.post("/api/waitlist", json={"email": "not-an-email"})
    assert r.status_code == 400
    assert sent_waitlist == []


def test_join_waitlist_rejects_non_string_email(client, sent_waitlist):
    r = client.post("/api/waitlist", json={"email": 123})
    assert r.status_code == 400
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_waitlist.py -v`
Expected: FAIL — `ImportError: cannot import name 'Waitlist'` (and no route yet).

- [ ] **Step 3a: Add the model**

In `models.py`, add this class immediately after the `PendingSignup` class (the imports `from datetime import datetime, timezone` are already present at the top):

```python
class Waitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

- [ ] **Step 3b: Create the route**

Create `routes/waitlist.py`:

```python
"""Public waitlist endpoint — records an email and sends a confirmation."""
import logging
import re

from flask import Blueprint, request, jsonify

from models import db, Waitlist
from utils.email_provider import get_email_provider

logger = logging.getLogger(__name__)

waitlist_bp = Blueprint("waitlist", __name__)

# Deliberately permissive: one @, a dot in the domain, no spaces. Real
# validity is proven by the confirmation email actually arriving.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@waitlist_bp.route("", methods=["POST"])
def join_waitlist():
    data = request.get_json(silent=True) or {}
    email_raw = data.get("email")
    if not isinstance(email_raw, str):
        return jsonify({"error": "Please enter a valid email address."}), 400
    email = email_raw.strip().lower()
    if not email or len(email) > 120 or not _EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    if db.session.query(Waitlist).filter_by(email=email).first() is not None:
        return jsonify({"status": "already"}), 200

    db.session.add(Waitlist(email=email))
    db.session.commit()

    # Best-effort: a send failure must not lose the recorded signup.
    try:
        get_email_provider().send_waitlist_confirmation(email)
    except Exception:
        logger.exception("waitlist confirmation email failed for %s", email)

    return jsonify({"status": "added"}), 200
```

- [ ] **Step 3c: Register the blueprint**

In `app.py`, add to the route-import block (alongside the other `from routes.X import X_bp` lines, ~53–68):

```python
    from routes.waitlist import waitlist_bp
```

and add to the registration block (alongside the other `app.register_blueprint(...)` calls, ~71–86):

```python
    app.register_blueprint(waitlist_bp, url_prefix="/api/waitlist")
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_waitlist.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Commit**

```bash
git add models.py routes/waitlist.py app.py tests/test_waitlist.py
git commit -m "feat(waitlist): add Waitlist model and POST /api/waitlist endpoint"
```

---

## Task 3: Gate signup behind an invite code

**Files:**
- Modify: `config.py`, `routes/auth.py`, `tests/conftest.py`
- Test: `tests/test_auth_gating.py`

- [ ] **Step 1: Write the failing tests**

First, in `tests/conftest.py`, add this near the other env setup at the top of the file (after the `os.environ["DATABASE_URL"] = "sqlite:///:memory:"` line, ~line 14) so a developer's shell value can't gate the existing register tests:

```python
# Signups are open in tests unless a test explicitly sets this.
os.environ.pop("SIGNUP_INVITE_CODE", None)
```

Then create `tests/test_auth_gating.py`:

```python
"""Invite-code gating on POST /api/auth/register (SIGNUP_INVITE_CODE)."""


def test_register_open_when_code_unset(client, sent_codes, monkeypatch):
    monkeypatch.delenv("SIGNUP_INVITE_CODE", raising=False)
    r = client.post(
        "/api/auth/register",
        json={
            "username": "openuser",
            "email": "open@example.com",
            "password": "password123",
        },
    )
    assert r.status_code == 202, r.get_json()


def test_register_blocked_without_code(client, sent_codes, monkeypatch):
    monkeypatch.setenv("SIGNUP_INVITE_CODE", "letmein")
    r = client.post(
        "/api/auth/register",
        json={
            "username": "gateduser",
            "email": "gated@example.com",
            "password": "password123",
        },
    )
    assert r.status_code == 403
    assert sent_codes == []  # no verification email on a blocked signup


def test_register_blocked_with_wrong_code(client, sent_codes, monkeypatch):
    monkeypatch.setenv("SIGNUP_INVITE_CODE", "letmein")
    r = client.post(
        "/api/auth/register",
        json={
            "username": "wrongcode",
            "email": "wrong@example.com",
            "password": "password123",
            "invite_code": "nope",
        },
    )
    assert r.status_code == 403


def test_register_allowed_with_correct_code(client, sent_codes, monkeypatch):
    monkeypatch.setenv("SIGNUP_INVITE_CODE", "letmein")
    r = client.post(
        "/api/auth/register",
        json={
            "username": "rightcode",
            "email": "right@example.com",
            "password": "password123",
            "invite_code": "letmein",
        },
    )
    assert r.status_code == 202, r.get_json()
    assert len(sent_codes) == 1  # verification email sent on success
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_auth_gating.py -v`
Expected: the `blocked` tests FAIL (register currently returns 202 with no gating).

- [ ] **Step 3a: Add the config var + prod guard**

In `config.py`, add after the `EMAIL_FROM = ...` line (line 61):

```python
    # Invite-only signup gate. When set, /api/auth/register requires a matching
    # `invite_code`. Empty = open signup (dev/test default).
    SIGNUP_INVITE_CODE = os.environ.get("SIGNUP_INVITE_CODE", "")
```

Then inside the `if _is_production():` block, add another check alongside the existing ones (before `if problems:`):

```python
        if not os.environ.get("SIGNUP_INVITE_CODE"):
            problems.append(
                "SIGNUP_INVITE_CODE must be set — signups are invite-gated in "
                "production (leave it unset only for an intentionally open launch)"
            )
```

- [ ] **Step 3b: Gate the register route**

In `routes/auth.py`, ensure `import os` is present at the top of the file (add it to the imports if missing). Then, inside `register()`, immediately after `data = request.get_json(silent=True) or {}` (line 41), add:

```python
    # Invite-only gate. Read live from the env (not Config) so tests can toggle
    # it per-case and prod can rotate it without a code change. Inactive when unset.
    required_code = (os.environ.get("SIGNUP_INVITE_CODE") or "").strip()
    if required_code:
        provided = data.get("invite_code")
        if not isinstance(provided, str) or provided.strip() != required_code:
            return jsonify(
                {
                    "error": "Sign-ups are invite-only right now. "
                    "Join the waitlist to request access."
                }
            ), 403
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_auth_gating.py tests/test_auth.py tests/test_auth_verification.py tests/test_config.py -v`
Expected: PASS — new gating tests pass; existing auth + config tests still pass (they don't set `SIGNUP_INVITE_CODE`, so gating stays off, and `test_config.py` only asserts failure/dev paths).

- [ ] **Step 5: Commit**

```bash
git add config.py routes/auth.py tests/conftest.py tests/test_auth_gating.py
git commit -m "feat(auth): gate signup behind SIGNUP_INVITE_CODE"
```

---

## Task 4: Wire the landing waitlist form

**Files:**
- Modify: `frontend/public/landing.html`

- [ ] **Step 1: Replace the fake submit handler**

In `frontend/public/landing.html`, the current handler (lines ~2714–2724) is:

```javascript
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!input.value || !input.value.includes("@")) {
      input.focus();
      return;
    }
    success.classList.add("show");
    input.value = "";
    if (window.__bingerySfx) window.__bingerySfx("swoosh");
    setTimeout(() => success.classList.remove("show"), 4000);
  });
```

Replace it with a real submission:

```javascript
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = (input.value || "").trim();
    if (!email || !email.includes("@")) {
      input.focus();
      return;
    }
    try {
      const resp = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await resp.json().catch(() => ({}));
      if (resp.ok && data.status === "already") {
        success.textContent = "You’re already on the waitlist.";
      } else if (resp.ok) {
        success.textContent = "✓ You’re on the list. Watch your inbox.";
        input.value = "";
      } else {
        success.textContent =
          (data && data.error) || "Something went wrong. Please try again.";
      }
    } catch (err) {
      success.textContent = "Network error. Please try again.";
    }
    success.classList.add("show");
    if (window.__bingerySfx) window.__bingerySfx("swoosh");
    setTimeout(() => success.classList.remove("show"), 4000);
  });
```

(The `#waitlistSuccess` div's static text is now overwritten via `textContent`; leaving its HTML as-is is fine.)

- [ ] **Step 2: Verify the build still succeeds**

Run (from `frontend/`): `npm run build`
Expected: build succeeds; Vite copies `public/landing.html` into `dist/`.

- [ ] **Step 3: Commit**

`frontend/dist/` is a build artifact regenerated at deploy. Check whether it is tracked: run `git status --short frontend/dist/landing.html`.
- If it prints nothing (gitignored/untracked): commit only the source —
  ```bash
  git add frontend/public/landing.html
  git commit -m "feat(landing): wire the waitlist form to POST /api/waitlist"
  ```
- If it shows the file as modified (tracked): include it —
  ```bash
  git add frontend/public/landing.html frontend/dist/landing.html
  git commit -m "feat(landing): wire the waitlist form to POST /api/waitlist"
  ```

---

## Task 5: Invite-code field in the React signup form

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/stores/auth.ts`, `frontend/src/features/auth/AuthForm.tsx`

- [ ] **Step 1: Add `invite_code` to the API client**

In `frontend/src/lib/api.ts`, change the `register` body type (line ~139) to include `invite_code`:

```ts
  register: (body: { email: string; password: string; username: string; display_name?: string; invite_code?: string }) =>
    request<RegisterPendingResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
```

- [ ] **Step 2: Thread it through the auth store**

In `frontend/src/stores/auth.ts`, change the `signUp` signature in the `AuthState` interface (line ~14) to:

```ts
  signUp: (body: { email: string; password: string; username: string; display_name?: string; invite_code?: string }) => Promise<void>;
```

The `signUp` implementation already forwards `body` to `api.register(body)`, so no other change is needed there.

- [ ] **Step 3: Add the field + waitlist link to AuthForm**

In `frontend/src/features/auth/AuthForm.tsx`:

(a) Add state after the `displayName` state (line ~17):

```tsx
  const [inviteCode, setInviteCode] = useState("");
```

(b) In `submit()`, add `invite_code` to the `signUp({...})` call (the register branch, ~lines 45–50):

```tsx
        await signUp({
          email: normEmail,
          password,
          username,
          display_name: displayName.trim() || undefined,
          invite_code: inviteCode.trim() || undefined,
        });
```

(c) In the register-mode fields block (currently the `<>...</>` at ~lines 179–195), add the invite-code input and a waitlist hint after the Display name input, so the block reads:

```tsx
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
          <Input
            label="Invite code"
            value={inviteCode}
            onChange={(e) => setInviteCode(e.target.value)}
            autoComplete="off"
          />
          <p className="text-xs text-text-muted">
            No invite code?{" "}
            <a href="/" className="text-amber hover:underline">
              Join the waitlist
            </a>
            .
          </p>
        </>
      ) : null}
```

(When gating is off the field is simply ignored by the backend; on a `403` the existing error display shows the "invite-only" message and the link points users to the landing waitlist.)

- [ ] **Step 4: Verify typecheck + build**

Run (from `frontend/`): `npm run build`
Expected: PASS (`tsc -b` clean + `vite build`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/stores/auth.ts frontend/src/features/auth/AuthForm.tsx
git commit -m "feat(auth): add invite-code field to the register form"
```

---

## Task 6: Full verification

**Files:** none (verification + manual smoke)

- [ ] **Step 1: Backend suite**

Run: `python -m pytest tests/test_waitlist.py tests/test_auth_gating.py tests/test_auth.py tests/test_auth_verification.py tests/test_email_provider.py tests/test_config.py -v`
Expected: all PASS. Then run the full suite once — `python -m pytest -q` — to confirm nothing else regressed.

- [ ] **Step 2: Frontend build**

Run (from `frontend/`): `npm run build`
Expected: clean.

- [ ] **Step 3: Manual smoke**

Run backend + `cd frontend && npm run dev`, then:
- On the landing page, submit the waitlist form with a new email → success message; resubmit the same email → "already on the waitlist"; (dev) confirm the Console provider logged the confirmation.
- Set `SIGNUP_INVITE_CODE` in the backend env and restart: try registering without a code → invite-only error; with the correct code → proceeds to the verify step.
- With the var unset, registration works as before.

- [ ] **Step 4: Final confirmation**

If Steps 1–3 are green, no extra commit is needed. Commit any smoke-fix separately with a descriptive message.

---

## Self-review

- **Spec coverage:** waitlist persistence + endpoint (Task 2) ✓; confirmation email (Tasks 1, 2) ✓; duplicate → "already on the waitlist" (Task 2 + Task 4 message) ✓; single shared invite-code gate active-when-set + prod boot guard (Task 3) ✓; landing form wired with three outcomes (Task 4) ✓; AuthForm invite field + waitlist link (Task 5) ✓; tests for waitlist, gating, and the email method (Tasks 1–3) ✓.
- **No placeholders:** every code step has complete code; every run step has an exact command + expected result. The only conditional is the Task 4 `dist/` commit, resolved by an explicit `git status` check.
- **Type/name consistency:** `send_waitlist_confirmation` is defined in Task 1 and called in Task 2's route and patched in Task 2's test fixture; `Waitlist` defined in Task 2 model, imported in Task 2 route + tests; `invite_code` flows api.ts (Task 5.1) → store (5.2) → AuthForm (5.3) → backend `data.get("invite_code")` (Task 3.3b); `SIGNUP_INVITE_CODE` read in both `config.py` (guard, Task 3.3a) and `routes/auth.py` (live check, Task 3.3b) and scrubbed in conftest (Task 3.1).
- **Out of scope (per spec):** per-invite codes, admin UI, rate-limiting/captcha, double-opt-in — none added.
