# Email Verification at Sign-Up — Design Spec

**Date:** 2026-06-10
**Status:** Approved design, ready for implementation planning
**App:** Bingery — https://bingery.fly.dev

---

## 1. What this document is

Add **email verification to sign-up**: registering sends a **6-digit code** to the given email; the account is only created — and a login token only issued — once the code is entered. Existing accounts are unaffected.

Two audiences:
1. **The implementation plan** (`docs/superpowers/plans/…`) executed in this repo (backend + frontend).
2. **Claude design** (claude.ai) — may generate the frontend step. It can read the repo, but Sections 4 and 9 spell out the contract and component spec explicitly so generation is unambiguous. **Section 4 is the output-format contract.**

---

## 2. Locked decisions

| Decision | Choice |
| --- | --- |
| **Gating model** | **Verify before create** — no `User` row and no JWT until the code checks out. A `pending_signup` row holds the attempt. |
| **Email delivery** | **Brevo** free tier (300/day) via its HTTP API using the existing `requests` dependency. Plus a **console** provider (logs the code) for dev/tests. **No new pip/npm dependencies.** |
| **Existing users** | Grandfathered automatically — they're untouched (no schema change to `user`). Seeded/demo users keep working: they're inserted directly into the DB, never passing through register. |
| **Code policy** | 6 digits, `secrets.randbelow(10**6)` zero-padded. TTL **10 min** · **5** wrong attempts per code · resend cooldown **60 s** · max **5** resends per pending signup. Code stored **bcrypt-hashed**. |
| **Migration** | None needed. New table only; `db.create_all()` (app.py:116) creates it on boot. |

---

## 3. Why verify-before-create (context for the implementer)

- No migration framework exists (no Alembic); `db.create_all()` adds **tables** but never **columns**, so an `email_verified` column would need a hand-written ALTER script against the production volume. A new table sidesteps that entirely.
- JWT issuance is the only gate needed: an unverified visitor simply never receives a token, so none of the app's `@jwt_required()` endpoints need changes.
- `login`, `GET/PATCH /me`, `restore()`, the `auth_headers` test fixture, and all seed scripts are untouched.

---

## 4. Output format & conventions (contract for generated code)

**Backend (Python/Flask)**
- Flask 3 blueprints; new endpoints live in `routes/auth.py` alongside register/login. Import the **existing module-level `bcrypt`** from `routes/auth.py` — do not instantiate a second `Bcrypt`.
- Error bodies: `jsonify({"error": "<string>"})` with 4xx status (matches the dominant convention; leave register's existing list-style validation response as-is).
- Email normalization must match login exactly: `.strip().lower()`.
- New model goes in `models.py` next to `User`; SQLAlchemy declarative style matching existing models.
- Config in `config.py` reading env vars, with production boot guards in the same block as the existing JWT/CORS guards (config.py:54-64 pattern).
- Provider module `utils/email_provider.py` mirrors `utils/ai_provider.py`'s shape: a `get_email_provider()` factory keyed on `EMAIL_PROVIDER`.
- Tests: pytest, in-memory SQLite fixtures from `tests/conftest.py`, `responses` lib (`@responses.activate`) for the Brevo HTTP mock — same pattern as `tests/test_ollama_provider.py`.

**Frontend (React/TS)**
- React 18 + TypeScript, Tailwind utility classes only, semantic token classes (`bg-surface`, `text-text-muted`, `text-danger`, `text-amber`, `border-border`…), default breakpoints.
- `@/` alias → `frontend/src/`. Conditional classes via `cn()` from `@/lib/cn`.
- Reuse primitives: `Input` (supports `label`, `error`, `leading`), `Button` (`variant`/`size`/`loading`), `GlassCard` from `@/design/*`. **No form library** — native HTML constraints + `useState`, matching `AuthForm.tsx`.
- API calls added to the `api` object in `frontend/src/lib/api.ts` following the `login`/`register` pattern; errors throw `ApiError` (message from the backend `error` field, plus `status`).
- Auth state in the zustand store `frontend/src/stores/auth.ts`.
- Mobile-first discipline: unprefixed = mobile, `md:` = desktop; ≥768px renders unchanged unless a change is purely additive.

---

## 5. Data model

New model `PendingSignup` in `models.py` (table `pending_signup`):

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer PK | |
| `email` | String(120), **unique**, indexed, not null | normalized (strip+lower) |
| `username` | String(80), not null | validated like register today |
| `password_hash` | String(128), not null | bcrypt, same as `User` |
| `display_name` | String(80), nullable | |
| `code_hash` | String(128), not null | bcrypt hash of the 6-digit code |
| `code_expires_at` | DateTime, not null | now + 10 min, set on issue/resend |
| `attempts_remaining` | Integer, not null, default 5 | decremented per wrong code |
| `resend_count` | Integer, not null, default 0 | |
| `last_sent_at` | DateTime, not null | cooldown anchor |
| `created_at` | DateTime, not null | for the 24 h lazy purge |

No `to_dict` needed (never serialized to clients). A module-level `_now()` helper (returns `datetime.utcnow()`) is used for every time comparison so tests can monkeypatch it.

---

## 6. Endpoints

### `POST /api/auth/register` (modified)
1. Validation identical to today (username ≥3, email contains `@`, password ≥6; same 400 list-style error body).
2. Uniqueness vs `user` table identical to today (two 409s).
3. **Lazy purge:** delete `pending_signup` rows with `created_at` older than 24 h.
4. Upsert pending: if a `pending_signup` exists for this email, **overwrite it** (new username/password/display_name, fresh code, attempts reset, `resend_count` reset) — the previous holder never proved ownership. **Send cooldown (security hardening, added in final review):** if the existing pending was emailed less than 60 s ago, register updates only the identity fields (username/password/display_name), keeps the already-emailed code valid, sends nothing, and still returns 202 — so an unauthenticated register loop cannot email-bomb an address or drain the Brevo quota.
5. Generate code, store bcrypt hash, set expiry/last_sent_at, **send the email**.
6. Success → **202** `{"verification_required": true, "email": "<normalized email>"}`. No token, no user.
7. Email send failure → roll back nothing (keep the pending row), return **503** `{"error": "Couldn't send the verification email. Please try again."}`.

### `POST /api/auth/verify` (new)
Body `{email, code}`. Normalize email; look up pending.
- Uniform failure — **all** of {no pending row, expired, attempts exhausted, wrong code} return **400** `{"error": "Invalid or expired code."}`. A wrong code decrements `attempts_remaining` first.
- On match: re-check username/email uniqueness against `user` (race guard; on conflict return the same 409s as register), create the `User` from the pending fields, delete the pending row, issue the JWT exactly like today's register (`create_access_token(identity=str(user.id))`).
- Success → **201** `{"token": <JWT>, "user": user.to_dict()}` — byte-compatible with today's register response.

### `POST /api/auth/resend` (new)
Body `{email}`. **Always** returns **200** `{"ok": true}` (anti-enumeration). Internally, only when a pending row exists:
- Cooldown: if `now - last_sent_at < 60 s` → silently no-op (still 200).
- Cap: if `resend_count ≥ 5` → silently no-op.
- Else: new code, reset `attempts_remaining` to 5, extend expiry 10 min, bump `resend_count`, send.

---

## 7. Email provider

`utils/email_provider.py`, mirroring the AI-provider pattern:

- `get_email_provider()` factory reads `EMAIL_PROVIDER` (`console` default, `brevo`).
- Interface: `send_verification_code(to_email: str, code: str) -> None`, raising `EmailSendError` on failure.
- **ConsoleProvider** — `logger.info("Verification code for %s: %s", to_email, code)`. Used in dev and as the test default.
- **BrevoProvider** — `requests.post("https://api.brevo.com/v3/smtp/email", headers={"api-key": BREVO_API_KEY}, json=…)`, timeout 10 s. Payload: sender `{"name": "Bingery", "email": EMAIL_FROM}`, the recipient, subject **"Your Bingery verification code"**, `textContent` and a minimal `htmlContent`: light background, the code in a large bold monospace block, "This code expires in 10 minutes. If you didn't create a Bingery account, ignore this email." Non-2xx or network error → `EmailSendError`.
- **Config (`config.py`):** `EMAIL_PROVIDER`, `BREVO_API_KEY`, `EMAIL_FROM`. **Production boot guard:** `FLASK_ENV=production` with `EMAIL_PROVIDER != "brevo"` or a missing `BREVO_API_KEY`/`EMAIL_FROM` → refuse to boot (same style as the existing secret/CORS guards).
- `.env.example` gains a documented block for the three vars.

---

## 8. Security notes

- Codes are never stored or logged in plaintext server-side (console provider excepted — that's its purpose, dev only).
- Brute force: ≤5 attempts/code × ≤6 codes (initial+5 resends) ≈ 30 guesses vs 10⁶ space.
- `verify` reveals nothing about whether an email has a pending signup; `resend` is constant-response.
- Register's existing username/email 409s already disclose existence — unchanged scope, not made worse.
- The pending row holds a bcrypt password hash, same protection as a real account.

---

## 9. Frontend flow

`AuthForm.tsx` gains a third step. Local state machine: `mode: "login" | "register"` (unchanged) plus `step: "form" | "verify"` with `pendingEmail: string`.

**Register submit:** `api.register(...)` now resolves `{verification_required, email}` → set `step="verify"`, `pendingEmail=email`. (Login is unchanged.)

**Verify step UI** (inside the same `GlassCard`):
- Heading: **"Check your email"** (`font-display`); body copy: "We sent a 6-digit code to **{pendingEmail}**." (`text-text-muted text-sm`).
- One code field using the existing `Input`: `label="Verification code"`, `inputMode="numeric"`, `pattern="[0-9]{6}"`, `maxLength={6}`, `autoComplete="one-time-code"` (iOS/Android autofill from the email), centered wide-tracked text (`text-center tracking-[0.4em] font-mono`). Single field, not 6 boxes (approved).
- Primary `<Button type="submit" loading>` **Verify** → `api.verifyEmail({email, code})`; success is handled exactly like a successful login: `api.setToken(res.token)`, store `{user, status:"authenticated"}`, `onSuccess()` → navigate `/discover`.
- **Resend** — a ghost text-button: "Resend code" disabled with a live countdown ("Resend in 42s") for 60 s after entry to the step and after each resend; calls `api.resendCode({email})`, shows "Code sent." confirmation line.
- **Back** — "Wrong email? Go back" text-button → returns to `step="form"` (register fields preserved).
- Errors render in the existing shared `<p className="text-sm text-danger">` (message from `ApiError`).

**Store (`stores/auth.ts`):** `signUp` no longer authenticates — it resolves the pending response and stays `idle` (the form drives the step). New actions `verifyEmail(body)` (sets loading → token+user on success, mirrors `signIn`) and `resendCode(body)` (fire-and-forget, surfaces errors). `AuthStatus` union unchanged.

**API client (`lib/api.ts`):** `register` return type becomes `{verification_required: true; email: string}`; new `verifyEmail(body: {email; code}): Promise<AuthResponse>`; new `resendCode(body: {email}): Promise<{ok: true}>`. Update `frontend/src/types/api.ts` accordingly.

Desktop and mobile share this layout (single column inside the auth card) — no breakpoint work needed.

---

## 10. Testing

`tests/test_auth_verification.py` (+ provider tests in `tests/test_email_provider.py`):

1. Register → 202, no token in body, no `User` row, one `PendingSignup` row, console provider captured the code (caplog).
2. Verify with correct code → 201 token+user, pending row deleted, login works afterward.
3. Wrong code → 400 uniform error, `attempts_remaining` decremented; 5 wrongs → subsequent correct code also rejected until resend.
4. Expired code (monkeypatch `_now`) → 400 uniform.
5. Resend: within 60 s → 200 but no new send; after cooldown → new code (old code stops working), attempts reset; 6th resend → no-op; unknown email → 200.
6. Re-register same email overwrites pending (new code, old code dead); register with a **verified** user's email → 409 unchanged.
7. Brevo provider: `responses` mock asserting URL, `api-key` header, payload fields; non-2xx → `EmailSendError`; register surfaces 503.
8. Production boot guard: production env + console provider → boot refusal.
9. Existing `tests/test_auth.py` register tests updated for the 202 contract; everything else (login, /me, fixtures) must pass untouched.

Frontend: `AuthForm` step transition + resend countdown covered by a Vitest test if practical; otherwise manual checklist in the plan.

---

## 11. Rollout

1. Brevo: create free account, verify the sender address (dashboard → Senders), copy an API key.
2. `fly secrets set EMAIL_PROVIDER=brevo BREVO_API_KEY=… EMAIL_FROM=…`
3. `fly deploy` — `db.create_all()` creates `pending_signup` on boot. No data migration.
4. Smoke: register with a real inbox on https://bingery.fly.dev, receive code, verify, land signed-in on /discover; confirm an existing account still logs in.

## 12. Out of scope

- Verifying existing accounts, change-email/change-password flows, password reset (natural follow-up reusing this plumbing).
- Rate-limiting middleware (Flask-Limiter) — per-code attempt caps cover this feature's risk.
- Magic links, OAuth, CAPTCHA.
