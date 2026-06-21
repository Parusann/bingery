# Signup Lock + Waitlist — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/signup-lock-waitlist`

## Problem

From the product owner's fix list:

> The hero page's waitlist form at the bottom should be operational and when
> signing up the user should receive a successful waitlist confirmation email. I
> also want the actual sign up to be locked with a code so that no one can make
> accounts yet and instead use the form to be waitlisted.

Today:

- The landing waitlist form is **cosmetic** — `frontend/public/landing.html`'s
  submit handler calls `preventDefault()`, fakes a success message, and makes no
  network call. Nothing is stored and no email is sent. There is no `Waitlist`
  model and no `/api/waitlist` route.
- Account signup is **fully open** — `routes/auth.py` `register()` accepts any
  email, gated only by 6-digit email verification (`PendingSignup`). There is no
  invite code anywhere.
- The transactional-email infrastructure **already works**:
  `utils/email_provider.py` has a provider factory (Console for dev, Brevo HTTP
  API for prod) selected by `EMAIL_PROVIDER`, but it only exposes
  `send_verification_code(to_email, code)`. Production refuses to boot unless
  `EMAIL_PROVIDER=brevo` + `BREVO_API_KEY` + `EMAIL_FROM` are set.

## Goals

1. **Make the waitlist real** — the landing form submits to the backend, the
   email is persisted, and the submitter receives a confirmation email.
2. **Lock signup behind a code** — account creation requires a shared invite
   code; without it, users are directed to the waitlist.

## Decisions (confirmed with product owner)

- **Single shared invite code** stored in an env var (`SIGNUP_INVITE_CODE`) — not
  per-invite/one-time codes.
- **Duplicate waitlist submit → explicit message** ("You're already on the
  waitlist"), not a silent success or a re-send.

## Non-goals (YAGNI)

- Per-invite / one-time / revocable codes; admin UI for code management.
- Rate-limiting, captcha, or bot protection beyond basic server-side validation.
- Double-opt-in (email-link confirmation) for the waitlist.
- Porting the hand-built `landing.html` waitlist section to React.

## Current state (from codebase map; exact lines re-verified at plan time)

- `frontend/public/landing.html` — standalone landing mockup served in the
  landing-route iframe. Contains `#waitlistForm` / `#waitlistEmail` /
  `#waitlistSuccess`; the submit handler fakes success with no `fetch`.
  `frontend/dist/landing.html` is the built copy actually served by Flask and
  must be rebuilt after editing the source.
- `routes/auth.py` — `register()` upserts a `PendingSignup`, generates a 6-digit
  code, calls `get_email_provider().send_verification_code(email, code)`;
  `verify()` creates the real `User`. This is where gating is added.
- `utils/email_provider.py` — `EmailProvider` Protocol + `ConsoleEmailProvider` +
  `BrevoEmailProvider`, each currently exposing only `send_verification_code`.
- `models.py` — `User`, `PendingSignup`. No `Waitlist` model, no `invite_code`.
- `config.py` — `EMAIL_PROVIDER` / `BREVO_API_KEY` / `EMAIL_FROM`; a production
  boot-guard block that fails fast if required prod vars are missing. No
  signup-gating flag yet.
- `app.py` — registers blueprints; `db.create_all()` runs at startup (a new model
  auto-creates on SQLite).
- `frontend/src/features/auth/AuthForm.tsx` — the real login/register/verify UI.
- `frontend/src/lib/api.ts` — `api.register(...)` etc.; no waitlist method.

## Approach

Wire the **existing** `landing.html` form to a new backend endpoint (a raw
`fetch`, then rebuild `dist`) rather than rebuilding the section in React. Gate at
the **register** endpoint so a missing/invalid code fails before any verification
email is sent. Both pieces reuse the existing email-provider factory and the
existing prod boot-guard pattern.

## Backend

### Invite-code gating
- `config.py`: read `SIGNUP_INVITE_CODE` (default empty). Gating is **active only
  when it is non-empty**, so local dev and the existing auth tests (which don't
  set it) keep working unchanged. Add `SIGNUP_INVITE_CODE` to the **production
  boot-guard** required-vars block so production cannot boot without it — i.e.
  accounts are locked the moment this ships to prod.
- `routes/auth.py` `register()`: if gating is active, read an `invite_code` field
  from the request JSON and compare with `SIGNUP_INVITE_CODE`. On mismatch/missing
  return `403 {"error": "Sign-ups are invite-only right now. Join the waitlist to
  request access."}` **before** creating a `PendingSignup` or sending any email.
  When gating is inactive, behavior is exactly as today.

### Waitlist
- `models.py`: new `Waitlist` model — `id` (pk), `email` (string, unique, not
  null, stored lowercased/trimmed), `created_at` (UTC default). `to_dict()` for
  symmetry with other models.
- New `routes/waitlist.py` blueprint, `POST /api/waitlist` (public, no auth):
  - Parse + normalize `email`; validate basic format. Invalid → `400 {"error":
    "Please enter a valid email address."}`.
  - If a `Waitlist` row already exists for that email → `200 {"status":
    "already"}` (no new row, no email).
  - Else insert the row, call
    `get_email_provider().send_waitlist_confirmation(email)`, and return `200
    {"status": "added"}`. (Email-send failures are caught/logged and do not fail
    the request — the email is recorded regardless.)
  - Register the blueprint in `app.py` under the `/api` prefix used by the others.

### Email provider
- Extend the `EmailProvider` Protocol with
  `send_waitlist_confirmation(to_email: str) -> None` and implement it in both
  `ConsoleEmailProvider` (log to stdout) and `BrevoEmailProvider` (send via the
  existing Brevo HTTP path, reusing `EMAIL_FROM`).
- Copy (tweakable): subject "You're on the Bingery waitlist"; body a short
  plain-text/HTML note confirming they'll be emailed when a spot opens.

## Frontend

### Landing form (`frontend/public/landing.html`)
- Replace the fake submit handler so it `fetch`es `POST /api/waitlist` with the
  email and renders one of three outcomes into the existing `#waitlistSuccess`
  region:
  - `status:"added"` → "You're on the list — check your inbox."
  - `status:"already"` → "You're already on the waitlist."
  - non-2xx / network error → a brief error message; keep the entered email.
- Use a relative URL (`/api/waitlist`) so it works on the same origin.
- Rebuild so `frontend/dist/landing.html` reflects the change (this is what Flask
  serves).

### AuthForm (`frontend/src/features/auth/AuthForm.tsx`)
- Add an invite-code input to the **register** step; include it in the
  `api.register(...)` payload (add the field to the API client + request type).
- On a `403` from register, show the invite-only message with a link to the
  landing waitlist (e.g. navigate to `/` / the landing `#waitlist` anchor).

## Testing

- **Waitlist** (`tests/`): add succeeds + sends confirmation (assert the provider
  method was invoked, mirroring the existing `sent_codes` capture fixture);
  duplicate email → `{status:"already"}`, no second send and no duplicate row;
  invalid email → `400`.
- **Gating** (`tests/test_auth*.py`): with `SIGNUP_INVITE_CODE` set —
  register without a code → `403`; wrong code → `403`; correct code → proceeds
  (PendingSignup created, verification email sent). With the var **unset** (the
  default in tests) — register behaves exactly as today (existing tests stay
  green).
- **Email provider** (`tests/test_email_provider.py`): `send_waitlist_confirmation`
  exists on the Console + Brevo providers and is callable.
- **Frontend**: covered by `tsc`/build for the AuthForm + API client change; the
  `landing.html` handler is plain HTML/JS verified by manual smoke.

## Rollout / risk

- Low-to-moderate. New model auto-creates (SQLite `create_all`). Gating is
  backward-compatible (off unless the env var is set) so nothing breaks in dev or
  in existing tests; production locks signup once `SIGNUP_INVITE_CODE` is set (and
  the boot guard ensures it is). The only build step is rebuilding `dist` after
  the `landing.html` edit.
- The duplicate-email "already on the waitlist" response intentionally reveals
  membership (product owner's choice); acceptable for a low-stakes waitlist.
