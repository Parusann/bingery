# Bingery — Feature Reference

A comprehensive, developer-facing tour of every Bingery feature: what it does,
how a user moves through it, the frontend components and backend endpoints
behind it, the data it owns, the env vars that tune it, and the edge cases worth
knowing. Ground truth is the live code — where an older spec or the README
disagrees with the implementation, this document follows the code.

Bingery is a Flask (Python) + React/TypeScript anime-tracking app: a curated
catalog sourced from AniList, a watchlist and episode tracker, ratings and
fan-genre voting, collections, an airing schedule with dub tracking, a
taste-based recommendation engine, and an AI chat assistant. Accounts are email
+ password with verification-code sign-up.

## Contents

1. [Accounts & Email Verification](#accounts--email-verification)
2. [Discover & Search](#discover--search)
3. [Anime Details & Franchise Strip](#anime-details--franchise-strip)
4. [Seasonal Browsing](#seasonal-browsing)
5. [Airing Schedule](#airing-schedule)
6. [Watchlist & Episode Tracking](#watchlist--episode-tracking)
7. [Collections](#collections)
8. [Ratings & Reviews](#ratings--reviews)
9. [Compare, Stats & Activity Feed](#compare-stats--activity-feed)
10. [For You — Recommendations](#for-you--recommendations)
11. [AI Chat Assistant](#ai-chat-assistant)
12. [Dub Reports & Admin](#dub-reports--admin)
13. [Mobile Experience & Design System](#mobile-experience--design-system)
14. [Architecture, Data Sync & Deployment](#architecture-data-sync--deployment)

---

## Accounts & Email Verification

Bingery accounts are email + password identities authenticated with JWTs. Sign-up is a two-phase flow: registering does **not** create a `User` row — it creates a `PendingSignup` row and emails a 6-digit verification code; only a successful code verification promotes the pending signup into a real account and returns a token. This guarantees every account owns a reachable email address before it can rate, vote, or chat, and it keeps unverified junk out of the `user` table entirely (abandoned signups are purged after 24 hours).

The verification endpoints are deliberately designed against account enumeration and code brute-forcing: failure modes return uniform responses, silent no-ops burn a bcrypt hash so timing doesn't leak whether a pending signup exists, codes are bcrypt-hashed at rest, and per-code attempt budgets are decremented atomically.

### User flow

1. User opens `/auth` (the `AuthPage` route) and toggles between **Sign in** and **Sign up** tabs on a single form.
2. **Sign up:** user enters username, optional display name, email, password. Submit calls `POST /api/auth/register`. On `202` the form swaps to the **verify step** ("Check your email") with a 6-digit code input and a 60-second resend countdown.
3. User types the code from the email (input strips non-digits, caps at 6, uses `autoComplete="one-time-code"`; the Verify button stays disabled until exactly 6 digits). Submit calls `POST /api/auth/verify`.
4. On success (`201`) the client stores the JWT, sets the user in the auth store, and navigates to `/discover`. On failure the uniform error "Invalid or expired code." is shown.
5. If the email never arrives, **Resend code** becomes clickable after the 60s countdown and calls `POST /api/auth/resend` (always appears to succeed). **"Wrong email? Go back"** returns to the form step so the user can re-register with a corrected email — re-registering overwrites the previous pending signup, since the prior holder never proved ownership.
6. **Sign in:** email + password to `POST /api/auth/login`; on `200` the token is stored and the user is signed in.
7. On every app boot, `main.tsx` calls `restore()`: if a token exists in `localStorage` it is validated via `GET /api/auth/me`; an invalid/expired token is silently cleared. Sign-out buttons in the header and mobile "More" sheet clear the token and reset the store.

### Frontend

- `frontend/src/features/auth/AuthPage.tsx` — page shell (GlassCard, heading), lazily mounted at the `auth` route in `frontend/src/routes.tsx`; redirects to `/discover` on success.
- `frontend/src/features/auth/AuthForm.tsx` — the whole flow in one component. Two axes of state: `mode` (`"login" | "register"`) and `step` (`"form" | "verify"`). Owns the client-side resend countdown (`RESEND_SECONDS = 60`, mirroring the server cooldown), the "Code sent." notice (cleared on verify submit), and normalizes email (`trim().toLowerCase()`) before `signUp`/`verifyEmail`/`resendCode` so client and server agree on the key.
- `frontend/src/stores/auth.ts` — Zustand store `useAuth` with `user`, `status` (`"idle" | "loading" | "authenticated" | "error"`), `error`, and actions `signIn`, `signUp` (sends the code, does *not* authenticate), `verifyEmail` (exchanges email+code for token and signs in), `resendCode`, `signOut`, `restore`.
- `frontend/src/lib/api.ts` — `api.login`, `api.register`, `api.verifyEmail`, `api.resendCode`, `api.me`, plus `getToken`/`setToken` persisting the JWT in `localStorage` under the key `bingery_token`. Every request attaches `Authorization: Bearer <token>` when a token exists.
- Response types in `frontend/src/types/api.ts`: `AuthResponse` (`{ token, user }`) and `RegisterPendingResponse` (`{ verification_required: true, email }`).
- `frontend/src/layout/Header.tsx` and `frontend/src/layout/MoreSheet.tsx` — sign-out buttons; `frontend/src/main.tsx` — boot-time `restore()` call.

### Backend

All routes live in `routes/auth.py` (blueprint `auth_bp`, prefix `/api/auth`). Email sending lives in `utils/email_provider.py`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | None | Validate input, upsert a `PendingSignup`, email a 6-digit code. Returns `202 {verification_required: true, email}`. `400` on validation errors, `409` if username/email already belongs to a real user, `503` if the email could not be sent. |
| POST | `/api/auth/verify` | None | Exchange email + correct code for a real `User` + JWT. `201 {token, user}` on success; uniform `400 {"error": "Invalid or expired code."}` for unknown email / expired / attempts exhausted / wrong code; `409` if the username or email was claimed in the meantime. |
| POST | `/api/auth/resend` | None | Re-issue a code (new code, fresh TTL, attempts reset). Always returns `200 {ok: true}` — cooldown, resend cap, missing pending signup, and even send failure are silent no-ops. |
| POST | `/api/auth/login` | None | Email + password → `200 {token, user}` (user includes stats). `401 {"error": "Invalid email or password."}` for both unknown email and wrong password. |
| GET | `/api/auth/me` | JWT | Current user's profile with stats (`total_ratings`, `total_genre_votes`, `average_score`). `404` if the token's user no longer exists. |
| PATCH | `/api/auth/me` | JWT | Update `username` (uniqueness checked, `409` on collision), `bio` (truncated to 500 chars), `avatar_url`, `display_name` (trimmed, capped 80 chars, empty → `null`). |

Notable server-side logic:

- **Code generation & storage.** Codes are `secrets.randbelow(10**6)` zero-padded to 6 digits, stored only as a bcrypt hash (`code_hash`). TTL is 10 minutes — `CODE_TTL_MINUTES` is defined once in `utils/email_provider.py` so the email copy can never drift from the enforced TTL.
- **Anti-enumeration / anti-timing-oracle.** `verify` returns the same body for every failure mode and burns a bcrypt check against a module-level dummy hash (`_DUMMY_CODE_HASH`) on the no-pending path so timing matches the wrong-code path. `resend` burns a bcrypt hash on every silent no-op for the same reason. `register` deliberately *does* return distinct `409`s for taken username/registered email — duplicate feedback at sign-up is a usability tradeoff; the uniform responses protect the unauthenticated code endpoints.
- **Brute-force budget.** Each code gets `attempts_remaining = 5`. Wrong guesses decrement via an atomic conditional `UPDATE ... WHERE attempts_remaining > 0` so concurrent wrong attempts can't stretch the budget through lost updates.
- **Register cooldown branch.** Re-submitting register for the same email within the 60s cooldown does not generate or send a new code (an unauthenticated register loop must not become an email cannon) — it returns `202` but keeps the already-emailed code valid, while still applying the latest username/password/display-name so a "fix my typo" re-submit wins at verify time.
- **Race handling.** Concurrent registers for one email are resolved via the unique-email `IntegrityError`: the loser keeps the winner's (already-emailed) code and applies its identity fields. `verify` re-checks username/email availability both before insert and again after an `IntegrityError`, mapping back to the same `409`s.
- **Lazy purge.** Every register call deletes `PendingSignup` rows older than 24 hours.
- **Email providers** (`utils/email_provider.py`, factory `get_email_provider()` keyed on `EMAIL_PROVIDER`):
  - `ConsoleEmailProvider` (default) — "sends" by logging `Verification code for <email>: <code>` at INFO. Dev/test only.
  - `BrevoEmailProvider` — POSTs to `https://api.brevo.com/v3/smtp/email` with a 10s timeout, plain `requests` (no SDK). Sends both text and HTML bodies branded "Bingery". Non-2xx responses raise `EmailSendError`; the Brevo response body (truncated to 500 chars) is logged server-side only.
  - Unknown provider names raise `ValueError` at call time.
- **JWT.** `flask_jwt_extended`; identity is the stringified user id; access tokens expire after 7 days (`config.py: JWT_ACCESS_TOKEN_EXPIRES`). There is no refresh token or server-side revocation — sign-out is purely client-side token deletion.

### Data model

`models.py`:

- **`User`** — `id`, `username` (unique, indexed), `email` (unique, indexed), `password_hash` (bcrypt), `avatar_url`, `bio` (≤500), `display_name` (nullable, ≤80), `created_at`, `taste_profile_cache`. Relationships to ratings, fan-genre votes, watchlist entries, collections. `to_dict(include_stats=True)` adds rating/vote counts and average score (login and `/me` include stats; `verify`'s response does not).
- **`PendingSignup`** — `id`, `email` (unique, indexed), `username`, `password_hash`, `display_name`, `code_hash`, `code_expires_at`, `attempts_remaining` (default 5), `resend_count` (default 0), `last_sent_at`, `created_at`. Never serialized to clients. All datetimes are naive UTC, set explicitly by `routes/auth.py` via the monkeypatchable `_utcnow()` (SQLite returns naive datetimes, so time math stays naive-to-naive).

Client state: the `useAuth` Zustand store (`user`, `status`, `error`) plus the JWT in `localStorage["bingery_token"]`. Pending-verification context (which email is awaiting a code) lives only in `AuthForm` component state — a page reload during the verify step drops back to the form, though the pending signup survives server-side.

### Configuration

| Setting | Default | Where | Effect |
|---|---|---|---|
| `EMAIL_PROVIDER` | `console` | env / `config.py` | `console` logs codes; `brevo` emails them. |
| `BREVO_API_KEY` | `""` | env | Brevo API key (required when provider is `brevo`). |
| `EMAIL_FROM` | `""` | env | Sender address for Brevo mail (must be a Brevo-validated sender). |
| `JWT_SECRET_KEY` | dev sentinel | env / `config.py` | JWT signing key. |
| `JWT_ACCESS_TOKEN_EXPIRES` | 7 days | `config.py` | Token lifetime. |
| `CODE_TTL_MINUTES` | 10 | `utils/email_provider.py` | Code lifetime; single source of truth for both enforcement and email copy. |
| `RESEND_COOLDOWN` | 60 s | `routes/auth.py` | Minimum gap between sends per email (applies to both `/resend` and register re-submits). |
| `MAX_RESENDS` | 5 | `routes/auth.py` | Resend cap per pending signup (register resets it to 0). |
| `PENDING_MAX_AGE` | 24 h | `routes/auth.py` | Pending signups older than this are purged lazily on register. |
| Attempts per code | 5 | `routes/auth.py` (`attempts_remaining`) | Wrong-guess budget; reset by each new code. |
| `RESEND_SECONDS` | 60 | `frontend/src/features/auth/AuthForm.tsx` | Client-side resend countdown mirroring the server cooldown. |

Production guard (`config.py`): with `FLASK_ENV=production` the app **refuses to boot** if `SECRET_KEY`/`JWT_SECRET_KEY` are still dev defaults, `CORS_ORIGINS` is `*`, `EMAIL_PROVIDER` isn't `brevo`, or Brevo is selected without `BREVO_API_KEY`/`EMAIL_FROM` (exit code 2 with a FATAL message listing the problems).

### Edge cases & limits

- **Validation floors:** username ≥ 3 chars (trimmed), email must contain `@`, password ≥ 6 chars. Multiple failures are joined into a single `400` error string. Email is normalized `trim().toLowerCase()` on both client and server.
- **Uniform failure responses:** `verify` never distinguishes unknown email vs expired vs exhausted vs wrong code (`400 "Invalid or expired code."`); `resend` returns `200 {ok: true}` no matter what; `login` returns the same `401` for unknown email and wrong password.
- **Resend semantics:** each successful resend issues a brand-new code, restores `attempts_remaining` to 5, extends expiry by the full TTL, and increments `resend_count`. After 5 resends, or within the 60s cooldown, resend is a silent no-op.
- **Send-failure paths differ by route:** register returns `503` and keeps the pending row (with `last_sent_at` already stamped — so an immediate retry lands in the cooldown branch and returns `202` *without* sending; the user must wait out the 60s and use Resend). `resend` rolls back and still returns `200`.
- **Re-register overwrites:** registering again for an email with a pending signup replaces the username/password/display name (and, outside the cooldown, the code). The previous submitter never proved ownership, so this is by design — and it's what powers "Wrong email? Go back".
- **Verify races:** a username or email claimed between register and verify produces a `409` at verify time even with a correct code; the same mapping is applied if the final commit hits an `IntegrityError`.
- **Code input UX:** the verify input filters to digits, hard-caps at 6, and the submit button is disabled until 6 digits — so most malformed submissions never reach the server.
- **No rate limiting beyond the above:** there is no per-IP throttle on `login` or `verify`; brute force on `verify` is bounded only by the 5-attempt budget and 10-minute TTL per code (max 6 codes per pending signup: initial + 5 resends).
- **No password reset, no email change, no token refresh/revocation** exist in the code. `PATCH /api/auth/me` is implemented server-side but `frontend/src/lib/api.ts` currently exposes no method that calls it.
- **`localStorage` access is wrapped in try/catch** — in environments where storage throws (e.g. blocked third-party storage), the app degrades to logged-out rather than crashing.
- **Verify response omits stats:** `verify` returns `user.to_dict()` without `include_stats`, while `login` and `GET /me` include stats — a freshly verified user object won't have `total_ratings` etc. until the next `restore()`/login.

---

## Discover & Search

Discover is the main catalog-browsing surface of Bingery: a paginated grid of anime cards that can be filtered by genre, narrowed by title search, and re-sorted, plus a debounced typeahead search box for jumping straight to a title's detail page. It exists so users can explore the locally-synced catalog (seeded from MAL/AniList data) without needing an account — all of its endpoints are public.

The feature also owns the app-wide NSFW policy: a two-tier genre filter (`Hentai` hard-blocked always, `Ecchi` soft-blocked behind an opt-in toggle) that is applied centrally to every list-style endpoint via `utils/nsfw.py` and surfaced in the UI as a persisted eye-icon toggle in the header.

### User flow

1. User lands on `/discover` (linked from the desktop `NavBar`, the mobile `BottomTabBar`, the mobile header's search icon, and as the post-login redirect from `AuthPage`).
2. The grid loads page 1 of the catalog, sorted by API score descending, NSFW-filtered per the global toggle. While loading, 12 skeleton cards render.
3. **Typeahead:** typing 2+ characters into the search box fires a debounced (250 ms) call to `/api/search/autocomplete`; a dropdown shows up to 8 suggestions (poster thumbnail, English-preferred title, year). Clicking a suggestion navigates to `/anime/:id` and clears the box.
4. **Full search:** pressing Enter instead submits the query — it is written to the URL as `?q=...` and the grid refetches `/api/anime?search=...`.
5. **Genre filter:** a horizontally-scrollable pill row (`All` + every tag in `FAN_GENRES`) sets `?genre=...`; the backend matches it against official genre names.
6. **Sort:** four sort buttons (`API score`, `Community score`, `Year`, `Title`) set `?sort=...`.
7. Changing any filter resets to page 1. Prev/Next buttons page through results (24 per page); the page number is component state, not URL state, so a refresh keeps `q`/`genre`/`sort` but returns to page 1.
8. **NSFW toggle:** the eye icon in the desktop `Header` (or mobile `MoreSheet`) flips Ecchi visibility app-wide. The tooltip states explicitly that Hentai is always hidden.
9. Clicking any `AnimeCard` navigates to the detail route `/anime/:id`.

### Frontend

- `frontend/src/features/discover/DiscoverPage.tsx` — route component at `/discover` (registered lazily in `frontend/src/routes.tsx`). Holds `q`/`genre`/`sort` in URL search params via `useSearchParams` and `page` in local state; composes the four components below.
- `frontend/src/features/discover/SearchAutocomplete.tsx` — controlled input + animated dropdown (framer-motion). Uses `useSearch`; outside-click closes the dropdown; Enter submits the trimmed query to the parent; suggestion click navigates to `/anime/{id}`.
- `frontend/src/features/discover/FilterBar.tsx` — genre pill row built from `FAN_GENRES` (`frontend/src/lib/genres.ts`) with per-genre colors from `genreColor()`, plus the four-button sort selector.
- `frontend/src/features/discover/AnimeGrid.tsx` — responsive 2/3/4/6-column grid; skeleton state (12 placeholders), empty state ("No anime found."), staggered `ScrollReveal` entrance per card.
- `frontend/src/features/discover/AnimeCard.tsx` — poster card with blur-up image load, score badge (community score preferred, falling back to `api_score`), English-preferred title, and up to 3 genre badges. Reused by other features (watchlist, seasonal, etc.).
- `frontend/src/hooks/useAnimeList.ts` — TanStack Query wrapper around `api.getAnime()`; builds the query string (`page`, `per_page=24`, `sort`, `order=desc`, optional `search`/`genre`); query key `["anime-list", page, perPage, search, genre, sort, order]`.
- `frontend/src/hooks/useSearch.ts` — debounced autocomplete hook (`minChars=2`, `delay=250` ms); errors silently resolve to an empty result list.
- `frontend/src/stores/nsfw.ts` — zustand store with `persist` (localStorage key `bingery-nsfw`); `visible` defaults to `false`.
- `frontend/src/layout/NsfwToggle.tsx` — shared toggle button (`aria-pressed`, eye/eye-off icon) rendered by `frontend/src/layout/Header.tsx` (desktop, `size="sm"`) and `frontend/src/layout/MoreSheet.tsx` (mobile, `size="lg"` with an On/Off label).
- `frontend/src/lib/api.ts` — `applyNsfwParam()` appends `include_nsfw=true` to any request whose path starts with one of `NSFW_AWARE_PREFIXES` (`/anime`, `/seasonal`, `/recommend`, `/schedule`) whenever the store says visible. The autocomplete path (`/search/autocomplete`) is deliberately not in that list.

### Backend

Blueprints: `routes/anime.py` (`anime_bp`, prefix `/api/anime`) and `routes/search.py` (`search_bp`, prefix `/api/search`), both registered in `app.py`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/anime` | None | Paginated catalog list. Params: `page`, `per_page` (default 20, max 100), `search` (ilike on `title`/`title_english`), `genre` (exact official-genre name), `sort` (`api_score`\|`year`\|`title`\|`episodes`, anything else falls back to `api_score`), `order` (`asc`\|`desc`), `include_nsfw`. NSFW-filtered via `maybe_exclude_nsfw`. |
| GET | `/api/anime/top` | None | Top anime by average community rating (subquery over `Rating`, `HAVING count >= 1`); `limit` default 10, max 50. NSFW-filtered. |
| GET | `/api/anime/genres` | None | All genres, both grouped by `category` and flat. Not called by the current frontend (FilterBar uses the static `FAN_GENRES` list instead). |
| GET | `/api/search/autocomplete` | None | Typeahead. `q` (min 2 chars, else empty 200), `limit` (default 8, max 20). Ranks exact-prefix matches on `title_english` first, then prefix on `title`, then substring; tie-break `api_score` desc nullslast. Returns minimal payload (id, titles, image, year, score, episodes, first 3 official genres). **No NSFW filtering.** |
| GET | `/api/search/full` | None | Advanced search: `q` (title/English title/synopsis ilike), `genres` (comma-separated, `IN` match), `year_min`/`year_max`, `min_score`, `status`, `sort` (`score`\|`year`\|`title`\|`newest`), `page`, `per_page` (default 24, max 100). Returns full `to_dict(include_community=True)` payloads. **No NSFW filtering. Not called by the current frontend** — `frontend/src/lib/api.ts` has no method for it. |

All endpoints query the local SQLite catalog only — no external API calls in the request path (the catalog is populated offline by `seed.py` / `sync_anilist.py`). All search matching uses SQL `ilike` substring matching; there is no full-text index.

NSFW logic lives in `utils/nsfw.py`:
- `HARD_BLOCKED_GENRES = ("Hentai",)` — excluded unconditionally, even with `?include_nsfw=true`.
- `SOFT_BLOCKED_GENRES = ("Ecchi",)` — excluded unless the request carries `?include_nsfw=true`.
- `maybe_exclude_nsfw(query)` applies both tiers via `NOT IN (subquery of anime_ids tagged with the blocked genres)` and is shared by `/api/anime`, `/api/anime/top`, `/api/seasonal`, `/api/schedule`, and the recommendation/chat pipelines.

### Data model

Owned/read tables (`models.py`):
- `Anime` — the catalog row: `mal_id`, `anilist_id`, `title`, `title_english`, `title_japanese`, `synopsis`, `api_score`, `popularity`, `year`, `season`, `episodes`, `studio`, `image_url`, `banner_url`, `status`, `source`. Search/sort operate on `title`, `title_english`, `synopsis`, `api_score`, `year`, `episodes`.
- `Genre` — `name` (unique), `category` (`standard` | `demographic` | `theme`, seeded in `seed.py`; AniList sync creates new ones as `standard` in `utils/anilist.py`).
- `anime_genres` — association table joining the two; genre filtering and NSFW blocking both go through it.
- `Rating` — read by `/api/anime/top` and by `to_dict(include_community=True)` to compute `community_score`/`rating_count` per row.

Client state:
- `useNsfw` zustand store (persisted to localStorage as `bingery-nsfw`): `{ visible: boolean }`, default `false`.
- TanStack Query cache: `["anime-list", ...]` entries with global defaults `staleTime: 30s`, `gcTime: 5min`, `refetchOnWindowFocus: false`, `retry: 1` (`frontend/src/lib/queryClient.ts`).
- URL search params `q`, `genre`, `sort` on `/discover` (shareable/bookmarkable); `page` is ephemeral component state.

### Configuration

- `VITE_API_URL` (frontend, optional) — backend origin when the SPA is hosted on a different origin; `/api` is appended automatically. Default: `http://localhost:5000/api` on localhost, same-origin `/api` otherwise (`frontend/src/lib/api.ts`).
- `HARD_BLOCKED_GENRES = ("Hentai",)`, `SOFT_BLOCKED_GENRES = ("Ecchi",)` — module constants in `utils/nsfw.py`; changing the policy means editing these tuples.
- `NSFW_AWARE_PREFIXES = ["/anime", "/seasonal", "/recommend", "/schedule"]` — which API paths get the `include_nsfw=true` opt-in appended (`frontend/src/lib/api.ts`).
- `useSearch(query, minChars = 2, delay = 250)` — autocomplete trigger threshold and debounce.
- Page sizes: backend `/api/anime` default `per_page=20` (cap 100); the Discover grid requests 24. Autocomplete default `limit=8` (cap 20); `/api/search/full` default `per_page=24` (cap 100); `/api/anime/top` default `limit=10` (cap 50).

### Edge cases & limits

- **Autocomplete bypasses the NSFW filter.** `routes/search.py` never calls `maybe_exclude_nsfw`, so Hentai/Ecchi-tagged titles can surface in the typeahead dropdown (and in `/api/search/full`) even though the grid hides them. The hard-block is only as wide as the endpoints that use `utils/nsfw.py`.
- **The "Community score" sort button is a silent no-op alias.** `FilterBar.tsx` offers `community_score`, but the backend's sort map in `routes/anime.py` only knows `api_score`/`year`/`title`/`episodes`; unknown keys fall back to `api_score`, so "API score" and "Community score" currently return identical ordering.
- **Genre pills can produce guaranteed-empty results.** `FilterBar` renders all ~80 `FAN_GENRES` tags, but `/api/anime?genre=` matches the official `Genre` table by exact name (about 29 seeded names). Picking a fan-only tag like "Wholesome" or "Mind-Bending" yields zero rows and the "No anime found." empty state.
- **Toggling NSFW does not invalidate the query cache.** The nsfw flag is injected at fetch time and is not part of any query key, and no `invalidateQueries` fires on toggle — so an already-rendered grid keeps showing the pre-toggle result set until the query refetches (remount after the 30 s `staleTime`; window-focus refetch is disabled).
- **Autocomplete dropdown shows a blank format.** `SearchAutocomplete` renders `a.format`, but the autocomplete endpoint doesn't return a `format` field, so only the year appears in the suggestion subtitle.
- Queries shorter than 2 characters return `{"results": []}` with 200 and never hit the network from the client; autocomplete network errors are swallowed and rendered as "no results".
- Pagination uses Flask-SQLAlchemy `paginate(error_out=False)`: out-of-range pages return an empty `anime` list with 200 rather than 404.
- Ascending sorts use `nullsfirst()`, so rows missing the sort field (e.g. no `year`) lead ascending result sets; descending sorts push them last via `nullslast()`.
- No rate limiting on any of these endpoints, and every keystroke past 2 chars (after debounce) is a live DB query — acceptable for the current SQLite-backed catalog size.
- `/api/search/full` applies `.distinct()` to avoid duplicate rows when multiple genres match; the multi-genre match is OR semantics (`Genre.name IN (...)`), not AND.
- Hard-block behavior is regression-tested in `tests/test_schedule_week.py::test_nsfw_hentai_excluded`.

---

## Anime Details & Franchise Strip

The anime detail page (`/anime/:id`) is the hub view for a single title: hero banner with poster, titles, genre badges and key stats, plus composed panels from other features (community fan genres, personal rating, watch status, collections, next-episode countdown, dub reporting, similar titles). It is readable logged-out; logging in adds the interactive panels and enriches the detail payload with the viewer's own rating, genre votes, and watch status.

The franchise strip ("Watch the rest in order!") sits under the fan-genre section and lists every entry in the same franchise — seasons, movies, OVAs, specials — as a wrapping grid of poster cards in ascending release order, with the currently viewed title highlighted. Relations are **not** stored in the local database (the `Anime` table has no relation, format, or precise-date columns), so the franchise is assembled live from the AniList GraphQL API at view time via a bounded breadth-first traversal, then mapped back onto the local catalog by `anilist_id`. Entries that exist in the catalog link to their Bingery detail page; entries we don't have are rendered from AniList data as non-clickable cards. Design rationale and locked decisions are in `docs/superpowers/specs/2026-06-01-related-franchise-strip-design.md` (note: the spec's traversal caps of 50/6 were shipped as 25/5 — code wins).

### User flow
1. User clicks any anime card (discover, watchlist, search, etc.) and lands on `/anime/:id`. Skeleton placeholders show while the detail query loads.
2. The hero renders: banner image (faded), poster, English title (romaji subtitle if different), up to 6 genre badges, and a stat grid (Episodes / Year / Format / Score). Logged-in users also see the watch-status selector and "add to collection" actions in the hero, a dub-report button below it.
3. Below the hero: next-episode widget, then a two-column layout — "Community fan genres" bars on the left, "Your rating" panel on the right.
4. The franchise strip loads independently (separate query). When the title belongs to a multi-entry franchise, "Watch the rest in order!" appears under the fan-genre card with one poster card per franchise entry, sorted oldest-first. Each card shows poster, format badge (TV / Movie / OVA / …), title, and release label ("Apr 2013"-style month+year, bare year, or "TBA").
5. The currently viewed title carries an amber "Current" badge and ring and is not clickable. Cards for catalog entries navigate to that entry's detail page; cards for titles not in the catalog are static (slightly dimmed, `opacity-90`).
6. Standalone titles (no franchise) show no strip at all — the section renders only when there are 2+ entries.

### Frontend
- **Route**: `anime/:id` in `frontend/src/routes.tsx`, lazy-loaded with a `Suspense` skeleton fallback, inside the `AppShell` layout.
- **`frontend/src/features/details/AnimeDetailPage.tsx`** — page orchestrator. Reads `:id` from `useParams`, runs three independent React Query hooks (`useAnimeDetail`, `useSimilar`, `useRelated`), and composes:
  - **`DetailHero.tsx`** — banner/poster/titles/genre `Badge`s/stat grid on a `LiquidGLSurface`; accepts an `actions` slot rendered only for logged-in users (`WatchStatusSelector` from `features/watchlist/`, `AddToCollection` from `features/collections/`).
  - **`RelatedStrip.tsx`** — the franchise strip. Wrapping grid (`grid-cols-2 md:grid-cols-3 lg:grid-cols-4`), 2:3 poster, format badge top-left, "Current" badge top-right. Returns `null` when `related.length <= 1`. Only entries with a local `id` that are not `is_current` are wrapped in `<Link to={/anime/${id}}>`.
  - **`SimilarStrip.tsx`** — "You might also like", up to 6 `AnimeCard`s (from `features/discover/`); hidden when empty. (See Edge cases: currently never renders due to an endpoint mismatch.)
  - Cross-feature panels documented in their own sections: `FanGenreBars.tsx`, `RatingPanel.tsx`, `NextEpisodeWidget.tsx`, `DubReportButton.tsx` (the latter shown only when logged in).
- **`frontend/src/hooks/useAnimeDetail.ts`** — `useAnimeDetail(id)` (key `["anime-detail", id]`), `useSimilar(id)` (`["anime-similar", id]`), `useRelated(id)` (`["anime-related", id]`); all `enabled: !!id`.
- **`frontend/src/lib/api.ts`** — `getAnimeDetail(id)` → `/anime/${id}`, `getSimilar(id)` → `/anime/${id}/similar`, `getRelated(id)` → `/anime/${id}/related`. Paths under `/anime` are NSFW-aware: when the global NSFW toggle (`stores/nsfw.ts`) is on, the client appends `include_nsfw=true` (both detail and related endpoints ignore it).
- **Types**: `RelatedEntry` / `RelatedResponse` / `AnimeDetailResponse` in `frontend/src/types/api.ts`; `AnimeSummary` / `AnimeDetail` in `frontend/src/types/models.ts`.

### Backend
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/anime/<int:anime_id>` | Optional JWT | Full detail (`to_dict(include_community=True)`): community score, rating count, aggregated fan genres. With a valid token, adds `user_rating`, `user_genre_votes`, `user_watch_status`. 404 if id unknown. |
| GET | `/api/anime/<int:anime_id>/related` | None | Same-franchise entries in release order, assembled live from AniList and mapped to the local catalog. 404 if id unknown; otherwise always 200. |

Both live in `routes/anime.py` (blueprint prefix `/api/anime`). The page also calls endpoints owned by other features: `/api/anime/<id>/episodes` (episode schedule), `/api/anime/<id>/review` + `/api/anime/<id>/fan-genres` (ratings), `/api/watchlist/anime/<id>` (watchlist), `/api/collections/...`, `/api/dub-reports`.

#### Detail endpoint logic
`get_anime` uses `verify_jwt_in_request(optional=True)`; any exception while resolving user context degrades gracefully to `user_rating: null`, `user_genre_votes: []`, `user_watch_status: null` rather than failing the request. Community fields are computed live per request (`Anime.get_community_score()`, `get_rating_count()`, `get_fan_genres()` — aggregate queries over `Rating` and `FanGenreVote`).

#### Related endpoint logic (`get_related` + `utils/anilist.py`)
1. If the anime has no `anilist_id` → `{"related": []}` (200).
2. `AniListClient.get_anime_relations(anilist_id)` runs the dedicated `RELATIONS_QUERY` (id, type, titles, format, `seasonYear`, `startDate`, cover art, plus one hop of `relations.edges`). It is deliberately self-contained — sent via `_execute()` without the shared `AnimeFields` fragment, so the catalog-sync payload is untouched. Results are normalized (`release_date` only when year+month+day are all present; title = english → romaji → "Unknown"; cover = large → medium; AniList `format` mapped through `FORMAT_LABELS`) and memoized in a module-level dict `_RELATIONS_CACHE` keyed by `anilist_id` with a 24 h TTL.
3. `assemble_franchise(start_id, fetch_relations)` does a breadth-first traversal over the one-hop relation graphs: it follows only edges whose `relationType` is in `FRANCHISE_RELATION_TYPES = {PREQUEL, SEQUEL, PARENT, SIDE_STORY, ALTERNATIVE}` and whose node `type == "ANIME"` (drops manga/novel ADAPTATION links, spin-offs, recaps, character links). Cycle-safe via an `enqueued` set; bounded by `FRANCHISE_MAX_NODES = 25` successful fetches and `FRANCHISE_MAX_DEPTH = 5` hops. A visited node's own data is authoritative; unvisited neighbors keep the stub display data from their parent's edge. Per-node fetch failures are skipped (`continue`) without aborting the traversal.
4. The route maps all assembled `anilist_id`s to local rows in a single `Anime.anilist_id.in_(...)` query. Catalog hits get `id`, prefer `title_english or title` and the local `image_url`; misses get `id: null` and AniList title/cover. The start title is flagged `is_current: true` and is always present.
5. Sorting: ascending by `(year or 9999, month or 99, day or 99, title.lower())` — fully dated entries first, undated last, ties broken alphabetically.
6. The whole assembly is wrapped in `try/except`; **any** AniList failure returns `{"related": []}` with 200 so the detail page is never broken by upstream errors.

`AniListClient` (shared with catalog sync) self-rate-limits to one request per `RATE_LIMIT_DELAY = 0.7 s`, uses a 15 s HTTP timeout, and on HTTP 429 sleeps for `Retry-After` (default 60 s) and retries. Backend behavior is covered by `tests/test_related.py` (mocked AniList client).

### Data model
- **`Anime`** (`models.py`): the feature reads `id`, `anilist_id` (unique, indexed, nullable — the join key to AniList; titles without it get no franchise strip), `mal_id`, `title`, `title_english`, `title_japanese`, `synopsis`, `api_score`, `popularity`, `year`, `season`, `episodes`, `studio`, `image_url`, `banner_url`, `status`, `source`, plus the `official_genres` many-to-many. Community fields come from `Rating` and `FanGenreVote` aggregates at request time.
- **Not stored**: inter-title relations, media format, and precise release dates — by design (spec decision); they are fetched live from AniList per view.
- **Server-side cache**: `_RELATIONS_CACHE` in `utils/anilist.py` — in-process `dict` of `anilist_id -> (fetched_at, normalized_relations)`, no persistence.
- **Client state**: React Query caches under `["anime-detail", id]`, `["anime-related", id]`, `["anime-similar", id]`. No Zustand store is owned by this feature (it reads `stores/auth.ts` and `stores/nsfw.ts`).

### Configuration
No environment variables are specific to this feature; tuning is via constants in `utils/anilist.py`:
- `ANILIST_API = "https://graphql.anilist.co"` — upstream endpoint (free, no API key).
- `RATE_LIMIT_DELAY = 0.7` s between AniList requests (stays under AniList's 90 req/min).
- `RELATIONS_CACHE_TTL = 86400` s (24 h) — per-title relations cache.
- `FRANCHISE_MAX_NODES = 25` — max AniList fetches per franchise assembly.
- `FRANCHISE_MAX_DEPTH = 5` — max relation hops from the start title.
- `FRANCHISE_RELATION_TYPES = {PREQUEL, SEQUEL, PARENT, SIDE_STORY, ALTERNATIVE}` — single source of truth for what counts as "same franchise".
- `FORMAT_LABELS` — AniList `MediaFormat` → display label (`TV_SHORT` → "TV Short", `MOVIE` → "Movie", etc.; unmapped formats become `null` and show no badge).
- HTTP timeout per AniList call: 15 s (hardcoded in `_execute`).
The frontend API base honors the app-wide `VITE_API_URL` (defaults to `http://localhost:5000/api` in dev, same-origin `/api` in prod).

### Edge cases & limits
- **Upstream isolation**: any AniList error on `/related` yields `[]` with 200 — the strip silently hides; the rest of the page is unaffected because it's a separate query.
- **Standalone titles**: the response still contains the current entry alone; `RelatedStrip` hides itself whenever `related.length <= 1`.
- **Traversal caps**: at most 25 relation fetches, 5 hops. Entries beyond the caps still render if a fetched parent's edges reference them (stub data), but their own relations are never explored — very large franchises can be truncated.
- **Cold-cache latency**: assembly is sequential at ≥ 0.7 s per uncached title, so a big franchise's first view can take ~15–20 s before the strip appears (the request thread is occupied that long); within the next 24 h it is served from cache. A 429 from AniList blocks the request for the full `Retry-After` (default 60 s) and the retry has no attempt cap.
- **Cache scope**: `_RELATIONS_CACHE` is in-process and unbounded (entries only expire lazily by TTL check). It's "effectively global" only because deployment runs a single gunicorn worker; scaling to multiple workers means per-worker caches (spec defers Redis).
- **Date handling**: `release_date` is emitted only when year, month, and day are all known; sort places undated entries last (`9999/99/99`); the card label falls back release_date → year → "TBA".
- **NSFW**: neither `/api/anime/<id>` nor `/api/anime/<id>/related` applies the NSFW filter (`maybe_exclude_nsfw` is only used on list endpoints), so any title is viewable by direct URL and franchise entries appear regardless of NSFW classification; the `include_nsfw` param the client appends is ignored here.
- **Unknown id**: the API returns 404, but `AnimeDetailPage` only branches on `isLoading || !data` — a failed detail query leaves the page on the skeleton state indefinitely (no error UI).
- **Similar strip**: `GET /api/anime/<id>/similar` (`routes/anime.py`) ranks the catalog against the seed via `utils/similarity.py` — rank-weighted AniList tag overlap + genres + fan genres + format + era + a quality prior, blended 70/30 with the per-user `rec_signals` score when a JWT is present. Same-franchise entries are excluded from results (returned separately in `franchise`), and `SimilarStrip` renders the top 6 with shared-tag badges. The older genre-overlap route `GET /api/recommend/similar/<int:anime_id>` (`routes/recommend.py`) still exists but has no frontend consumers.
- **Hero field mismatches**: `DetailHero` reads `anime.format` and `anime.description`, but the backend sends `synopsis` and the `Anime` table has no format column — so the "Format" stat always shows "—" and the synopsis paragraph never renders on the detail page. (Format *is* shown correctly on franchise-strip cards, which get it live from AniList.)
- **Title display differs by source**: catalog entries on the strip show `title_english or title` (romaji); non-catalog entries show AniList's english-then-romaji choice — the same franchise can mix title languages.

---

## Seasonal Browsing

Seasonal Browsing lets a signed-in user view the anime lineup for any anime season (winter / spring / summer / fall) of any year, served entirely from Bingery's local database rather than a live AniList call. Each result carries a per-user watchlist overlay (`user_status`, `is_favorite`) so the API response already knows which shows the caller tracks. It exists so users can answer "what aired (or will air) in season X of year Y?" without leaving the app, complementing Discover (full catalog search/filter) and Schedule (day-by-day airing calendar).

### User flow

1. The user clicks **Seasonal** in the desktop nav bar (`NavBar`) or the mobile **More** sheet (`MoreSheet`, leaf icon) and lands on `/seasonal`.
2. The page opens on the *current* season, derived client-side from the browser clock: months Jan–Mar → winter, Apr–Jun → spring, Jul–Sep → summer, Oct–Dec → fall, plus the current year.
3. A heading shows "<season> <year>" (e.g. "spring 2026"); next to it the `SeasonPicker` offers `‹`/`›` buttons to step the year down/up one at a time and four toggle buttons (winter / spring / summer / fall) to switch season.
4. Every change triggers a fresh `GET /api/seasonal?year=…&season=…`; while loading, a 12-card skeleton grid renders.
5. Results display in the shared `AnimeGrid` of poster cards (title, score badge, up to 3 genre badges); clicking a card navigates to `/anime/:id`.
6. If the season has no rows, an empty state shows "No anime found for this season." with a link to `/discover`.
7. Season/year selection is component-local state — it is not reflected in the URL, so refreshing or revisiting always resets to the current season (no deep-linking to a specific season).

### Frontend

- `frontend/src/features/seasonal/SeasonalPage.tsx` — page component. Holds `year`/`season` in `useState`, seeded from `currentSeason()`; renders the heading, `SeasonPicker`, and `AnimeGrid`. Registered lazily at path `seasonal` in `frontend/src/routes.tsx` under the `AppShell` layout.
- `frontend/src/features/seasonal/SeasonPicker.tsx` — controlled picker: previous/next year buttons (no bounds) and one button per season from the local `SEASONS` constant (`["winter", "spring", "summer", "fall"]`). Calls `onChange(year, season)` upward.
- `frontend/src/hooks/useSeasonal.ts` — `useSeasonal(year, season)` wraps a TanStack Query with key `["seasonal", year, season]` calling `api.getSeasonal`; also exports `currentSeason(now)` (the month→season mapping above). No per-hook `staleTime` override, so global defaults from `frontend/src/lib/queryClient.ts` apply: `staleTime` 30 s, `gcTime` 5 min, `retry: 1`, no refetch on window focus.
- `frontend/src/lib/api.ts` — `api.getSeasonal(year?, season?)` issues `GET /seasonal?year=…&season=…` (query string only added when both are set). `/seasonal` is listed in `NSFW_AWARE_PREFIXES`, so when the global NSFW store (`frontend/src/stores/nsfw.ts`, persisted as `bingery-nsfw`) has `visible: true`, the client appends `include_nsfw=true`.
- Shared rendering: `frontend/src/features/discover/AnimeGrid.tsx` (responsive 2–6 column grid, skeleton + empty states) and `frontend/src/features/discover/AnimeCard.tsx` (poster card; shows `community_score ?? api_score` — seasonal payloads omit `community_score`, so cards display the AniList score).
- Navigation entries: `frontend/src/layout/NavBar.tsx` and `frontend/src/layout/MoreSheet.tsx`.

### Backend

Blueprint `seasonal_bp` in `routes/seasonal.py`, registered in `app.py` with `url_prefix="/api/seasonal"`.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/seasonal?season=<SEASON>&year=<YYYY>[&include_nsfw=true]` | JWT required | List anime matching season+year, alphabetical by title, with the caller's watchlist overlay. Returns `{"year", "season" (lowercased), "anime": [...]}`. |
| GET | `/api/seasonal/airing-now[?include_nsfw=true]` | JWT required | List anime whose `status` is currently airing, same overlay and ordering. Returns `{"anime": [...]}`. **No frontend consumer today** — exercised only by tests. |

Server-side logic:

- **Validation** — `season` is upper-cased and must be in `VALID_SEASONS` (`WINTER/SPRING/SUMMER/FALL`); otherwise 400 with `{"error": "season must be one of [...]"}`. `year` is required and must parse as int; missing → 400 "year is required", non-int → 400 "year must be an integer".
- **Vocabulary tolerance** — season matching uses `func.lower(Anime.season)` and airing-status matching uses `func.lower(Anime.status).in_(AIRING_STATUSES)` (`{"releasing", "currently_airing", "currently airing"}`), so both raw AniList enums (`WINTER`, `RELEASING`) and the human-readable forms stored by ingestion (`winter`, `Currently Airing`) match. Covered explicitly by `tests/test_seasonal.py::test_seasonal_matches_production_vocabulary`.
- **Watchlist overlay** — `_with_status_overlay` runs one bulk `WatchlistEntry` query for the caller (`anime_id IN (...)`) and stamps `user_status` (or `null`) and `is_favorite` onto each `Anime.to_dict(include_community=False)` payload. `include_community=False` skips the per-anime community score / rating count / fan-genre aggregation for list performance. Overlay isolation per user is test-covered.
- **NSFW filtering** — both endpoints pass their query through `maybe_exclude_nsfw` (`utils/nsfw.py`): Hentai-tagged anime are always excluded (hard block, even with `include_nsfw=true`); Ecchi-tagged anime are excluded unless the request opts in with `?include_nsfw=true`.
- **Data sourcing** — request-time reads hit only the local `anime` table; there is no live AniList call in this route. The `season`/`year` columns are populated by AniList ingestion (`utils/anilist.py`): `season` is mapped from the AniList `season` enum to lowercase via `season_map`, `year` comes from `seasonYear` falling back to `startDate.year`. The catalog is loaded/refreshed by `sync_anilist.py`, a resumable CLI sync that chunks AniList's catalog by `seasonYear` (1960 → current+1) to dodge AniList's 5000-offset pagination cap, sleeping `PAGE_SLEEP_SECONDS = 0.7` between pages (~85 req/min against AniList's 90 req/min limit). Targeted backfills are possible via `python -m utils.anilist --mode seasonal --season WINTER --year 2024`.
- No server-side caching, pagination, or background jobs in the route itself.

### Data model

- `Anime` (`models.py`): owns the columns this feature filters on — `year` (`Integer`, nullable) and `season` (`String(20)`, nullable; stored lowercase by ingestion, comment says "spring, summer, fall, winter") — plus `status` for `/airing-now`. Neither `year` nor `season` is indexed, and the season filter wraps the column in `lower()`, so both endpoints scan the anime table.
- `WatchlistEntry` (`models.py`): read-only dependency providing `status` and `is_favorite` for the overlay (unique per `user_id`+`anime_id`).
- `Genre` / `anime_genres` (`models.py`): read by the NSFW subquery filters.
- Client state: TanStack Query cache entries keyed `["seasonal", year, season]`; component-local `year`/`season` `useState` in `SeasonalPage`; the persisted zustand NSFW store (`bingery-nsfw` in localStorage) influences the request URL. Types: `Season` and `SeasonalResponse` in `frontend/src/types/models.ts` (re-exported as `SeasonalResp` in `frontend/src/types/api.ts`).

### Configuration

No env vars are specific to this feature. Relevant constants:

- `VALID_SEASONS = {"WINTER", "SPRING", "SUMMER", "FALL"}` and `AIRING_STATUSES = {"releasing", "currently_airing", "currently airing"}` — `routes/seasonal.py`.
- `HARD_BLOCKED_GENRES = ("Hentai",)`, `SOFT_BLOCKED_GENRES = ("Ecchi",)` — `utils/nsfw.py`.
- `PAGE_SLEEP_SECONDS = 0.7` — `sync_anilist.py` (ingestion pacing, not request-time).
- `NSFW_AWARE_PREFIXES = ["/anime", "/seasonal", "/recommend", "/schedule"]` — `frontend/src/lib/api.ts`.
- React Query defaults (`staleTime: 30_000`, `gcTime: 5 * 60_000`, `retry: 1`, `refetchOnWindowFocus: false`) — `frontend/src/lib/queryClient.ts`.
- `VITE_API_URL` — general API base-URL override (frontend-wide, not seasonal-specific).

### Edge cases & limits

- **Status codes**: 400 for invalid season, missing year, or non-integer year; 401 without a valid JWT. All 400 paths are covered in `tests/test_seasonal.py`.
- **No route guard**: `/seasonal` is reachable without logging in; the JWT-protected fetch then fails with 401, React Query retries once, and the page falls through to the empty state ("No anime found for this season.") rather than redirecting to `/auth` — there is no global 401 handler in `frontend/src/lib/api.ts`.
- **Unbounded year navigation**: `SeasonPicker` has no min/max on the year steppers; far-past or far-future years simply return empty lists.
- **No pagination or result cap**: the endpoint returns every matching row in one response, ordered alphabetically by `Anime.title`. A dense modern season is a few hundred rows at most, but nothing limits it.
- **Unindexed, non-sargable filter**: `func.lower(Anime.season)` defeats any index; both endpoints effectively table-scan `anime` (~25k rows for a full catalog sync).
- **Overlay returned but not rendered**: `user_status`/`is_favorite` are computed per result, but `AnimeCard` does not display them, so the seasonal grid currently shows no watchlist markers — the data is available for future UI.
- **`/airing-now` is dormant**: implemented and tested, but no frontend code calls it.
- **NSFW toggle staleness**: the seasonal query key omits the NSFW flag and the toggle does not invalidate queries, so flipping it does not refetch an already-cached season; the new filtering applies on the next fetch (key change, 30 s staleness, or remount). Hentai remains hard-blocked regardless of the toggle.
- **Coverage gap from ingestion**: AniList entries with `seasonYear: null` (mostly unscheduled specials/OVAs) are unreachable by the year-chunked catalog sync; a per-`format` "orphan-catcher" query in `utils/anilist.py` backfills most of them, but anything with a null/unmapped `season` column can never match a seasonal query.
- **Client clock dependency**: the initial season/year comes from `new Date()` in the browser, so a wrong local clock lands the user on the wrong season.
- **Data freshness**: results only change when the sync scripts run; there is no on-demand refresh from AniList at request time.

---

## Airing Schedule

The Airing Schedule is a week-anchored release calendar at `/schedule` that shows which anime episodes come out on each day, split by sub and dub. It exists because sub and dub releases of the same episode land weeks apart, and users tracking dubs in particular have no single reliable source; Bingery merges AniList sub dates, real dub sources, user-submitted dub reports, and a synthetic dub projection into one timeline, and is explicit (via an "estimated" tag) about which dates are guesses.

The same backend blueprint also powers the "next episode" pill on the anime detail page (`NextEpisodeWidget`), so per-episode air-date logic lives in one place.

### User flow

1. User clicks "Schedule" in the top nav (`frontend/src/layout/NavBar.tsx`) or the mobile bottom tab bar (`frontend/src/layout/BottomTabBar.tsx`).
2. If not signed in, the page renders a "Sign in to see the schedule" placeholder instead of the calendar (both schedule endpoints are JWT-protected).
3. On first load with no `?week` param, the page computes the Sunday of the current week **in the user's local timezone** and rewrites the URL to `?week=YYYY-MM-DD` (replace, not push). Full URL state is `?week=YYYY-MM-DD&lang=sub|dub|both&mine=0|1`, so any view is deep-linkable and survives refresh.
4. The header offers a `SUB | DUB | BOTH` segmented control plus a "My shows" star toggle (`mine`). Changing either rewrites the search params, which re-keys the React Query fetch.
5. A sticky `DayStrip` shows the month, ISO week number, prev/next-week chevrons, and seven day chips (short weekday + day number, an episode-count badge, and a glowing "TODAY" treatment on the current local date). Chevrons shift `?week` by ±7 days; day chips do **not** change the URL — they smooth-scroll to that day's section.
6. The page body is seven `DaySection`s in order. Each starts with a `DayBanner` (poster-art collage of up to 3 of the day's shows, weekday headline, episode count, watchlist count), then a gold-bordered group of watchlisted episodes, a divider, and the remaining episodes. The page deliberately loads scrolled to the top of the week rather than auto-jumping to today (a code comment in `SchedulePage.tsx` documents this choice); each day ends with a "Back to top" button.
7. Each `EpisodeRow` shows the poster, English-preferred title, `EP n` chip, the air time converted to the **user's local time** with the local timezone abbreviation, a SUB (peach) or DUB (sage) badge, an "estimated" tag when the dub date is synthetic, and a gold star overlay when the show is on the user's watchlist. Clicking a row navigates to `/anime/:id`.
8. Separately, on the anime detail page, `NextEpisodeWidget` shows pills like "Episode 12 (sub) airs in 2d 5h" for the next upcoming sub and dub episodes.

### Frontend

Route: `/schedule`, lazy-loaded in `frontend/src/routes.tsx` (line 78). Components live in `frontend/src/features/schedule/`:

- `SchedulePage.tsx` — owner of URL state (`useSearchParams`), auth gate (`useAuth` from `frontend/src/stores/auth`), week defaulting, scroll-to-day handler, per-day episode counts (memoized for `DayStrip` badges), and a 7-skeleton loading state.
- `ScheduleHeader.tsx` — page title + `FilterPills.tsx` (the `SUB|DUB|BOTH` segmented control and the "My shows" toggle; pure presentational, callbacks up to the page).
- `DayStrip.tsx` — sticky week navigator. Renders a single row on ≥768px and a two-row stacked layout below that (44px chevrons, full-width chip grid). Contains local helpers `shiftDay`, `monthOf`, and `isoWeekOf` (ISO-8601 week number computation).
- `DaySection.tsx` — splits episodes into watchlist vs. others (`on_watchlist`), hides "others" entirely when `myShowsOnly` is on, renders `DayBanner` + `EpisodeRow`s + back-to-top.
- `DayBanner.tsx` — collage banner; takes the first 3 episodes of the day as background art with per-position CSS mask gradients (`maskFor` handles 1/2/3-image variants), 168px tall when empty ("No releases") vs. 232px otherwise.
- `EpisodeRow.tsx` — one episode occurrence; gold-tinted variant for watchlisted shows.
- `Badge.tsx` — SUB/DUB pill (peach vs. sage, `sm`/`md` sizes).
- `EstimatedTag.tsx` — dashed "estimated" pill with `title` tooltip: "Dub date is estimated based on previous release cadence."
- `utils.ts` — all date/timezone helpers: `todayIsoDate`/`toLocalIsoDate` (local-date ISO), `toIsoDate` (UTC), `getSundayOfWeek` (local-timezone Sunday), `shiftWeek` (UTC ±7-day math on the ISO string), `formatLocalTime` (local `toLocaleTimeString`), `formatLocalTzAbbr` (Intl short TZ name with a `GMT±n` fallback), `formatWeekdayLong`/`formatWeekdayShort`/`dayNumber` (format the bucket date **as UTC** so labels match backend bucketing).

Data layer:

- `frontend/src/hooks/useScheduleWeek.ts` — React Query, key `["schedule-week", week, lang, mine]`, `staleTime: 60_000`, disabled until `week` exists.
- `frontend/src/hooks/useSchedule.ts` — `useAnimeEpisodes` (key `["anime-episodes", animeId]`), used by `frontend/src/features/details/NextEpisodeWidget.tsx` and `frontend/src/features/details/DubReportButton.tsx`. (The legacy `useSchedule`/`/schedule/upcoming` hook was removed 2026-06-28.)
- `frontend/src/lib/api.ts` — `getScheduleWeek`, `getAnimeEpisodes`. `/schedule` and `/anime` are in `NSFW_AWARE_PREFIXES`, so when the global NSFW toggle (zustand store `frontend/src/stores/nsfw`) is on, requests get `?include_nsfw=true` appended automatically.
- Types in `frontend/src/types/models.ts`: `ScheduleWeekEpisode`, `ScheduleWeekDay`, `ScheduleWeekResponse`, and `Episode`/`AnimeEpisodesResponse` (the latter now carry `dub_source` + `dub_estimated`). The legacy `ScheduleEpisode`/`ScheduleDay`/`ScheduleResponse` types were removed with `/upcoming`.

### Backend

Two endpoints live in `routes/schedule.py` (`schedule_bp`), registered at `url_prefix="/api"` in `app.py`.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/schedule/week` | JWT | One Sunday-anchored 7-day window of episodes, grouped by UTC date; supports `week` (required, `YYYY-MM-DD`), `lang` (`sub`/`dub`/`both`, default `both`), `mine` (`0`/`1`, default `0`). Powers the `/schedule` page. |
| GET | `/api/anime/<int:anime_id>/episodes` | JWT | Full episode list for one anime plus `next_sub`/`next_dub` (earliest strictly-upcoming episode per kind). Each episode carries `dub_source` + `dub_estimated`. Powers `NextEpisodeWidget` and `DubReportButton`. |

The legacy `/api/schedule/upcoming` endpoint (and its unused `useSchedule` hook) was **removed** in the 2026-06-28 schedule-consistency pass; `/week` is the sole timeline. Dub ingestion also exposes an admin endpoint (`routes/admin.py`, `url_prefix="/api/admin"`):

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/admin/ingest-dub-dates` | `X-Admin-Secret` | Batch-ingest corroborated real dub dates (`dub_source="research"` default) by `anilist_id`/`title` match; fills NULL/synthetic, preserves authoritative sources unless `overwrite`. The monthly `bingery-dub-research` task posts here. |

Server-side logic worth knowing:

- **Windowing**: `/week` parses `week` as UTC midnight and selects `[week, week+7d)`. It does **not** validate that the date is a Sunday — any anchor date yields a 7-day window starting there.
- **Bucketing & shape**: episodes are bucketed by the UTC date of their air timestamp. The response always contains exactly 7 (or `days`) day objects, including empty ones, sorted ascending. Within a day: ascending air time, tie-broken by lowercased romaji `title`.
- **Dual rows for `both`**: sub and dub are collected as separate passes over `Episode.air_date_sub` and `Episode.air_date_dub`, so one episode with both dates in-window produces two entries (`type: "sub"` and `type: "dub"`). The frontend keys rows by `id` + `type` accordingly.
- **`estimated` flag**: `true` exactly when `type == "dub"` and `Episode.dub_source == "synthetic_lag_8w"` (`SYNTHETIC_TAG` from `seed_dub_schedule.py`). `/api/anime/<id>/episodes` exposes the same signal per episode as `dub_estimated` (alongside the raw `dub_source`), so the detail page labels an estimated dub exactly like the timeline.
- **Watchlist annotation**: `_watchlisted_anime_ids` queries `WatchlistEntry.anime_id` for the JWT user (string identity cast to `int` — documented in-code as necessary to avoid a silently empty result). `mine=1` filters to those ids; every `/week` row carries `on_watchlist`.
- **NSFW filtering**: every query passes through `maybe_exclude_nsfw` (`utils/nsfw.py`) — anime tagged Hentai are always excluded; Ecchi is excluded unless `?include_nsfw=true`.
- **Datetime convention**: `Episode` air dates are stored as naive UTC. Query bounds strip tzinfo before binding; outputs are normalized to ISO-8601 with a trailing `Z` (`_as_iso_z`, naive values assumed UTC).
- **No caching layer and no external API calls at request time** — endpoints read only from the local DB. Episode data is populated offline by:
  - `sync_anilist.py` — full-catalog AniList sync; upserts `Episode` rows keyed `(anime_id, episode_number)` with `air_date_sub` from AniList `airingAt` epoch seconds, `sub_source="anilist"`. Rate-limited at ~85 req/min (`PAGE_SLEEP_SECONDS = 0.7`).
  - `utils/dub_sources/crunchyroll.py` (Tier 1) — parses Crunchyroll's public RSS feed (`CR_RSS_URL`), fuzzy-matches titles, writes `dub_source="crunchyroll_rss"`.
  - `utils/dub_sources/animeschedule.py` (Tier 2) — AnimeSchedule.net API; only fills NULL dub dates (Tier 1 wins).
  - `routes/dub_reports.py` (Tier 3) — an accepted user dub report **unconditionally** overwrites `air_date_dub` and sets `dub_source="user:<username>"` (highest precedence).
  - `seed_dub_schedule.py` — synthetic filler: projects `air_date_sub + lag` (each show's learned median sub→dub gap when it has real dub data, else the 56-day default) onto the top-N airing anime, tagging `dub_source="synthetic_lag_8w"`. It never overwrites rows from real sources (`crunchyroll_rss`, `animeschedule`, `research`, `user:%`), even with `--overwrite`; supports `--dry-run`, `--reset` (wipe synthetic rows), `--top N`, `--recent-window-days N`. Implemented as a bulk SQL `UPDATE` (the ORM version was OOM-killed on Fly's 256MB machines).

### Data model

Owned table — `Episode` (`models.py`):

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `anime_id` | Integer FK → `anime.id` | indexed, not null |
| `episode_number` | Integer | not null; unique with `anime_id` (`unique_anime_episode`) |
| `air_date_sub` | DateTime (naive UTC) | nullable, indexed |
| `air_date_dub` | DateTime (naive UTC) | nullable, indexed |
| `sub_source` | String(40) | default `"anilist"` |
| `dub_source` | String(40) | nullable; one of `crunchyroll_rss`, `animeschedule`, `research`, `user:<username>`, `synthetic_lag_8w` |
| `created_at` / `updated_at` | DateTime | auto-managed |

Dependencies: `Anime` (display title prefers `title_english` over `title`; `image_url` for posters; `api_score`/`status` drive the synthetic-seed cohort), `WatchlistEntry` (`on_watchlist`/`mine`), `Genre` + `anime_genres` (NSFW filtering), and `DubReport` (writes back into `Episode` on acceptance).

Client state: URL search params (`week`, `lang`, `mine`) are the source of truth for the view; React Query caches under `["schedule-week", week, lang, mine]` and `["anime-episodes", animeId]`; the NSFW zustand store changes the request URL (and thus the cache entry contents) globally.

### Configuration

- `lang` default `"both"` (`/week`); `mine` default `"0"`.
- React Query `staleTime`: 60 000 ms for `useScheduleWeek`.
- `seed_dub_schedule.py`: `SYNTHETIC_TAG = "synthetic_lag_8w"`, `LAG_DAYS = 56`, `--top` default 400, `DEFAULT_RECENT_WINDOW_DAYS = 90`.
- `ANIMESCHEDULE_API_KEY` env var — AnimeSchedule.net API token (`utils/dub_sources/animeschedule.py`; can also be passed explicitly).
- `CR_RSS_URL = "https://feeds.feedburner.com/crunchyroll/rss"`, `FETCH_TIMEOUT = 30` s in both dub ingesters.
- No feature flags; the endpoints ship unconditionally.

### Edge cases & limits

- **Timezone split-brain is by design**: day buckets and day labels are UTC (frontend formats bucket dates with `timeZone: "UTC"`), but each row's air time renders in the user's local timezone with a TZ abbreviation chip. An episode airing 23:30 UTC Tuesday shows under Tuesday's banner even if that is Wednesday morning local time. The "TODAY" chip compares the user's **local** date against UTC bucket dates, so near local midnight the highlighted chip can disagree with where "tonight's" episodes sit.
- **Week anchor**: the frontend always sends a local-timezone Sunday, but the backend accepts any valid date as the window start — a hand-edited `?week=` mid-week deep link works, just with a non-Sunday-aligned strip.
- **Param validation**: missing/garbage `week` → 400 `{"error": "week parameter required (YYYY-MM-DD)"}`; garbage `lang`/`kind` → 400; garbage `mine` → silently treated as `0` (truthy values: `1`, `true`, `yes`, `on`); garbage `days` → silently 7.
- **Unknown anime** on `/api/anime/<id>/episodes` → 404 `{"error": "anime not found"}`.
- **Duplicate appearances**: with `lang=both`, a show can legitimately appear twice in one week (sub row and dub row), each with its own badge.
- **`next_sub`/`next_dub`** exclude anything strictly in the past (`air < now`); an episode airing exactly "now" still counts as upcoming. `NextEpisodeWidget` renders nothing when there is no upcoming episode of either kind, and its relative countdown ("2d 5h") is computed at render time, not live-ticking.
- **Synthetic dub dates** fill the gaps: real dub coverage depends on a valid `ANIMESCHEDULE_API_KEY` (when unset, AnimeSchedule 401s and most dub rows fall back to projections flagged `estimated`). Restoring the token, the monthly `research` ingest, or an accepted user report replaces them and the tag disappears, since `dub_source` is no longer the synthetic tag. See `docs/runbooks/dub-schedule.md`.
- **NSFW**: Hentai never appears in the schedule under any setting; Ecchi appears only with the global toggle on.
- **`mine=1` belt-and-braces**: the backend filters to watchlisted anime, and `DaySection` additionally drops non-watchlist rows client-side, so a stale cache can't leak others' rows into "My shows" view.
- **Empty days still render** — `DayBanner` shows a shorter "No releases" banner; the strip chip simply omits its count badge.
- **Banner collage** uses at most the first 3 episodes of the day (sorted order), with mask variants for 1/2/3 images; days with one or two episodes get a sparser collage (a known-gap note in the spec).
- **No pagination or row caps** on either endpoint — a heavy day returns every row.
- **No request-time caching** beyond the 60 s client `staleTime`; every navigation past that refetches.
- **Estimated dubs avoid false precision**: synthetic dub rows render "time TBD" in the timeline and "expected ~<date>" in the detail widget (never a fake clock time or live countdown); the `estimated` tag's tooltip explains the date itself is approximate.

---

## Watchlist & Episode Tracking

The watchlist is the per-user library at the heart of Bingery: every anime a user interacts with gets a `WatchlistEntry` row recording a watch status (one of `watching`, `completed`, `plan_to_watch`, `dropped`, `on_hold`), an episode-progress counter, a favorite flag, and free-text notes. It exists so the rest of the app has a single source of truth for "what is this user's relationship to this show" — the stats dashboard, activity feed, weekly schedule highlighting, seasonal views, and recommendation signals all read from it.

Watchlist entries reference the **local** anime catalog (`Anime` rows), which is populated from AniList via the sync machinery in `routes/anilist.py` + `utils/anilist.py`. Ratings and watchlist status are deliberately decoupled (you can plan-to-watch without rating), but rating an anime auto-promotes its watchlist entry to `completed`.

### User flow

1. A signed-in user opens an anime detail page (`/anime/:id`). The page header shows the `WatchStatusSelector`: five status pills plus a "Favorite" toggle, pre-filled from `user_watch_status` in the detail response.
2. Clicking a pill optimistically highlights it, then fires `POST /api/watchlist/anime/:id` with the chosen status. Clicking the **already-active** pill removes the anime from the watchlist entirely (`DELETE`). On a failed save the pill reverts to the last server value.
3. Toggling Favorite flips `is_favorite`; if the anime wasn't tracked yet, this silently creates a `plan_to_watch` entry.
4. Rating an anime (the rating/review flow) auto-creates a `completed` watchlist entry, or upgrades an existing `plan_to_watch` entry to `completed`. The review endpoint additionally accepts an explicit `watch_status` override.
5. The user visits `/watchlist` (linked from `NavBar` and `BottomTabBar`). They see status tabs ("All" + one per status, each with a live count) and a responsive grid of poster cards showing their personal score and the fan-genres they assigned. Clicking a tab filters server-side; clicking a card returns to the detail page.
6. Elsewhere, the weekly schedule page highlights airing episodes whose anime is on the user's watchlist (`on_watchlist` flag) and offers a "my shows only" filter.

Signed-out users hitting `/watchlist` get an inline "Sign in to track" prompt rather than a redirect.

### Frontend

- `frontend/src/routes.tsx` — lazy-loads `WatchlistPage` at path `watchlist`.
- `frontend/src/features/watchlist/WatchlistPage.tsx` — page shell: reads the user from `useAuth` (`frontend/src/stores/auth`), holds the selected status tab in local state, renders skeletons / empty state / card grid.
- `frontend/src/features/watchlist/StatusTabs.tsx` — exports the canonical `STATUSES` array (key, label, accent color per status) used by both the tabs and the selector; renders "All" plus per-status pill buttons with counts from the stats query.
- `frontend/src/features/watchlist/WatchlistCard.tsx` — poster tile with a `★ n/10` badge (or "unrated"), up to 6 fan-genre `Badge`s with a `+N` overflow indicator, linking to `/anime/:id`.
- `frontend/src/features/watchlist/WatchStatusSelector.tsx` — inline status pills + favorite toggle rendered on `frontend/src/features/details/AnimeDetailPage.tsx`. Keeps optimistic local state (`selected`, `fav`), re-syncs from props when the detail query refetches, reverts on mutation error.
- `frontend/src/hooks/useWatchlist.ts` — TanStack Query layer: `useWatchlist(status?)` (key `["watchlist", status ?? "all"]`), `useWatchlistStats()` (key `["watchlist-stats"]`), and mutations `useSetWatchStatus`, `useToggleFavorite`, `useRemoveFromWatchlist`. Every mutation invalidates `["watchlist"]`, `["watchlist-stats"]`, **and** `["anime-detail", animeId]` so the detail page's pills reflect saved changes.
- `frontend/src/lib/api.ts` — `getWatchlist`, `getWatchlistStats`, `setWatchStatus` (body accepts optional `episodes_watched`), `toggleFavorite`, `removeFromWatchlist`.
- `frontend/src/types/models.ts` — `WatchStatus` union, `WatchEntry`, `WatchStats`, and `AnimeDetail.user_watch_status`.
- Consumers outside the feature: `frontend/src/features/schedule/DaySection.tsx`, `DayBanner.tsx`, `EpisodeRow.tsx` read the per-episode `on_watchlist` flag to group/highlight the user's shows.

### Backend

Blueprint: `watchlist_bp` in `routes/watchlist.py`, URL prefix `/api/watchlist`. All endpoints require a JWT.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/watchlist` | JWT | Paginated list of the user's entries. Query params: `status` (filter), `sort` (`title` \| `updated`), `page`, `per_page` (default 50, max 100). Returns `entries` (with embedded anime, score, genres), `total`, `page`, `pages`. |
| GET | `/api/watchlist/stats` | JWT | Count per status plus `total` and `favorites`. |
| GET | `/api/watchlist/anime/<anime_id>` | JWT | The user's entry for one anime, or `{"entry": null}` (200 either way). |
| POST | `/api/watchlist/anime/<anime_id>` | JWT | Upsert: sets `status` (default `plan_to_watch`), optionally `episodes_watched`, `is_favorite`, `notes`. 400 on invalid status, 404 on unknown anime. |
| DELETE | `/api/watchlist/anime/<anime_id>` | JWT | Remove the entry. 404 if not tracked. |
| POST | `/api/watchlist/anime/<anime_id>/favorite` | JWT | Toggle `is_favorite`; auto-creates a `plan_to_watch` entry if none exists. |
| POST | `/api/watchlist/bulk` | JWT | Bulk add: `{"anime_ids": [...], "status": "..."}`. Caps at the first 100 ids, skips unknown ids and already-tracked anime, returns `{"added": n, "status": ...}`. |
| POST | `/api/anilist/sync` | JWT | (In `routes/anilist.py`.) Imports/updates catalog `Anime` rows from AniList — modes `popular`, `top`, `trending`, `seasonal`, `search`; `pages` capped at 10. Watchlist entries can only reference anime that exist locally, so this is how trackable titles appear. |

Notable server-side logic:

- **Sorting**: `sort=title` joins `Anime` and orders by title ascending; everything else (including the accepted-but-unimplemented `sort=score`) orders by `WatchlistEntry.updated_at` descending.
- **Serialization**: `WatchlistEntry.to_dict(include_anime=True)` (in `models.py`) embeds the anime (without community aggregates) plus two per-entry lookups — the user's `Rating.score` and their `FanGenreVote` tags — so the watchlist grid renders score + genres without extra round-trips.
- **Auto-watchlist from ratings** (`routes/ratings.py`): the rate endpoint creates a `completed` entry or upgrades `plan_to_watch` → `completed`; the review endpoint additionally honors a `watch_status` override from the request body.
- **Detail enrichment** (`routes/anime.py`): `GET /api/anime/<id>` uses optional JWT verification and attaches `user_watch_status` when logged in.
- **Cross-feature reads**: `routes/schedule.py` computes the user's watchlist anime-id set to flag `on_watchlist` on weekly episodes; `routes/stats.py`, `routes/activity.py`, `routes/rec_signals.py`, and `routes/seasonal.py` also query `WatchlistEntry`.
- **AniList sync** (`utils/anilist.py`): `sync_anime_from_anilist` pages through the AniList GraphQL API (`https://graphql.anilist.co`, no auth key) and upserts via `sync_anime_to_db`, matching existing rows by `anilist_id` first, then `mal_id`. Requests are throttled with a 0.7 s delay to stay under AniList's 90 req/min limit.

### Data model

`WatchlistEntry` (`models.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `user_id` | Integer FK → `user.id`, indexed | |
| `anime_id` | Integer FK → `anime.id`, indexed | |
| `status` | String(20), default `plan_to_watch` | Valid values in `WATCH_STATUSES` (`models.py`): `watching`, `completed`, `plan_to_watch`, `dropped`, `on_hold` |
| `episodes_watched` | Integer, default 0 | Clamped to >= 0 on write |
| `is_favorite` | Boolean, default false | |
| `notes` | Text, nullable | Truncated to 1000 chars on write |
| `created_at` / `updated_at` | DateTime (UTC) | `updated_at` auto-bumps on any update (drives default sort and the stats activity heatmap) |

Constraint: `UNIQUE(user_id, anime_id)` (`unique_user_anime_watchlist`). Relationships: `user.watchlist_entries` and `anime.watchlist_entries` (both lazy dynamic backrefs).

Depends on `Anime` (catalog rows synced from AniList; `anilist_id` / `mal_id` unique keys), `Rating`, and `FanGenreVote` for the enriched list payload. `migrate_watchlist.py` is a one-shot backfill script that creates `completed` entries from pre-existing ratings (skips itself if the table already has data).

Client state: TanStack Query caches under `["watchlist", status|"all"]`, `["watchlist-stats"]`, and `["anime-detail", id]`; the selector keeps transient optimistic state locally.

### Configuration

No feature-specific environment variables. Tuning lives in code constants:

- `WATCH_STATUSES` — `models.py` (the five statuses; mirrored as `STATUSES` with colors in `frontend/src/features/watchlist/StatusTabs.tsx`).
- List pagination — `per_page` default 50, hard max 100 (`routes/watchlist.py`).
- Bulk add cap — first 100 ids per request (`routes/watchlist.py`).
- Notes cap — 1000 characters (`routes/watchlist.py`).
- AniList sync — `RATE_LIMIT_DELAY = 0.7` s between requests, sync `pages` capped at 10 per call (`utils/anilist.py`, `routes/anilist.py`).

### Edge cases & limits

- **`sort=score` is a no-op**: `routes/watchlist.py` accepts it but the branch is identical to the default — it sorts by `updated_at` descending, not by score. Only `title` and `updated` actually differ.
- **Episode tracking is API-only today**: `episodes_watched` exists in the model, the upsert endpoint, and the API client signature, but no frontend component sends or displays it — it stays 0 unless written directly via the API. There is also no upper-bound check against `Anime.episodes`.
- **Bulk add has no frontend caller**: it exists for onboarding/import scripts. It silently skips ids that don't resolve to an `Anime` and never modifies the status of entries that already exist.
- **Removing = clicking the active pill**: deselecting a status deletes the whole row, which also discards `is_favorite`, `notes`, and `episodes_watched` for that anime.
- **Favorite-first tracking**: favoriting an untracked anime creates a `plan_to_watch` entry — favorites are counted across all statuses in `/stats`.
- **Rating auto-completion is conservative**: a plain rating only upgrades `plan_to_watch` → `completed`; it never demotes `watching`/`dropped`/`on_hold`. The review endpoint's `watch_status` body field is the only rating-path way to set those.
- **Invalid input handling**: bad status on upsert → 400 listing valid statuses; unknown anime → 404; an invalid `status` query param on the list endpoint is silently ignored (returns all entries, no error); GET for an untracked anime returns 200 with `entry: null`.
- **N+1 on the list endpoint**: `to_dict(include_anime=True)` issues a rating query and a genre-vote query per entry, so a full 100-entry page costs ~200 extra queries. `/stats` likewise runs one COUNT per status (6 queries). Fine at current scale; worth knowing before adding statuses or raising page caps.
- **Catalog dependency**: you can only track anime already synced into the local DB. The AniList sync endpoint requires only a valid JWT (any logged-in user can trigger imports), wraps upstream failures as 502, and dedupes by `anilist_id`/`mal_id` so re-syncs update rather than duplicate.
- **Optimistic UI**: status and favorite changes render immediately on the detail page and revert on mutation error; consistency elsewhere relies on the triple cache invalidation in `frontend/src/hooks/useWatchlist.ts`.
- **Minor naming traps**: the chatbot tool `get_user_watchlist` (`routes/chatbot_tools.py`) actually returns the user's *ratings*, not `WatchlistEntry` rows; and the frontend types `removeFromWatchlist` as `{ ok: boolean }` while the server returns `{ "message": ... }` (the value is unused, so this is benign).

---

## Collections

Collections are user-curated, named lists of anime — distinct from the watchlist's fixed status buckets. A user can create any number of collections (e.g. "Cozy SoL", "Best of 2024"), add or remove anime from any anime detail page, and optionally mark a collection public, which mints an unguessable share token for a read-only link. Collections are private by default and scoped strictly to their owner.

### User flow

1. Signed-out users hitting `/collections` see a static "Sign in to build collections" prompt; nothing loads.
2. Signed-in users reach `/collections` from the top nav (`NavBar`) or the mobile "More" sheet. The page shows a responsive card grid of their collections, newest-updated first, each card showing name, Public/Private badge, item count, and last-updated date.
3. **Create**: the "New collection" button opens a modal with `CollectionForm` (name, description, "Public" checkbox). On success the app navigates to the new collection's detail page.
4. **Add items**: on an anime detail page (`/anime/:id`), signed-in users get an "Add to collection" popover listing all their collections; clicking a row adds the anime (a brief checkmark confirms). The popover also has an inline "New collection title…" field that creates a collection and then auto-adds the current anime to it.
5. **Detail page** (`/collections/:id`): grid of `AnimeCard`s for each item. Owners get a hover-revealed "Remove" button per card, an "Edit" button (same form in a modal), and a "Delete" button guarded by a `window.confirm`. Deleting navigates back to `/collections`.
6. **Share**: ticking "Public" in the edit form generates a share token. A "Copy share link" button then appears (only when a token exists) and copies `{origin}/collections/share/{token}` to the clipboard. Unticking "Public" deletes the token, permanently invalidating the link; re-enabling generates a fresh token.

### Frontend

- `frontend/src/features/collections/CollectionsListPage.tsx` — list page; skeleton grid while loading, empty state, create modal.
- `frontend/src/features/collections/CollectionCard.tsx` — grid card; maps the stored `color` token to one of five Tailwind gradient pairs (`amber`, `violet`, `indigo`, `rose`, `emerald`), falling back to amber.
- `frontend/src/features/collections/CollectionDetailPage.tsx` — detail page; owner check is `user?.id === c.user_id`; renders edit modal, delete, share button, and the item grid.
- `frontend/src/features/collections/CollectionForm.tsx` — shared create/edit form. Only sends `name`, `description`, `is_public` (never `color`/`icon`).
- `frontend/src/features/collections/AddToCollection.tsx` — popover used by `frontend/src/features/details/AnimeDetailPage.tsx` (rendered only when a user is signed in). The create-then-add path waits 60 ms after creation, then finds the new row via a `data-add-row="{id}"` DOM query and programmatically clicks it.
- `frontend/src/features/collections/ShareButton.tsx` — clipboard copy of the share URL; renders nothing when `share_token` is null.
- `frontend/src/hooks/useCollections.ts` — TanStack Query hooks: `useCollections`, `useCollection`, `useSharedCollection`, `useCreateCollection`, `useUpdateCollection`, `useDeleteCollection`, `useAddToCollection`, `useRemoveFromCollection`. Mutations invalidate `["collections"]` and/or `["collection", id]`.
- `frontend/src/lib/api.ts` — client methods `getCollections`, `getCollection`, `getSharedCollection`, `createCollection`, `updateCollection`, `deleteCollection`, `addToCollection`, `removeFromCollection`; JWT attached as `Authorization: Bearer` from `localStorage`.
- `frontend/src/types/models.ts` — `Collection`, `CollectionItem`, `CollectionDetail` interfaces.
- Routes in `frontend/src/routes.tsx`: `collections` and `collections/:id`, both lazy-loaded inside `AppShell`.

### Backend

Blueprint: `routes/collections.py`, registered in `app.py` at `url_prefix="/api/collections"`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/collections` | JWT | List the caller's collections, ordered by `updated_at` desc (no items, includes `items_count`). |
| POST | `/api/collections` | JWT | Create a collection. `name` required, ≤ 80 chars (400 otherwise). Returns 201 with the collection. |
| GET | `/api/collections/<id>` | JWT | Fetch one owned collection with its full `items` array. 404 if not owned. |
| PATCH | `/api/collections/<id>` | JWT | Partial update of `name`, `description`, `color`, `icon`, `is_public`. Toggling `is_public` manages the share token (see below). |
| DELETE | `/api/collections/<id>` | JWT | Delete the collection; items cascade-delete. Returns 204. |
| POST | `/api/collections/<id>/items` | JWT | Add an anime. `anime_id` must be an integer (400) referencing an existing `Anime` (404). Returns 201, or 200 with the existing item if already present. |
| DELETE | `/api/collections/<id>/items/<anime_id>` | JWT | Remove an anime from the collection. Returns 204 whether or not it was present. |
| GET | `/api/collections/public/<token>` | None | Public read-only view by share token; only matches when `is_public` is true. 404 otherwise. |

Notable server-side logic:

- **Ownership**: every owner endpoint resolves the collection via `_owned_or_404`, which filters by `(id, user_id)` and aborts 404 — non-owners get the same response as a nonexistent id (no 403, no existence leak).
- **Share tokens**: setting `is_public: true` generates a 16-character URL-safe token via `utils/tokens.py` `generate_share_token()` (`secrets.token_urlsafe(16)[:16]`), looping until unique against the `share_token` unique column. Setting `is_public: false` nulls the token, so old links are dead even if the collection is later re-published (a new token is minted).
- **Public serialization**: `Collection.to_dict(public=True)` omits `user_id` and `share_token` from the response.
- No caching, background jobs, or external API calls.

### Data model

`models.py`:

- **`collections`** (`Collection`): `id`, `user_id` (FK → `user.id`), `name` (String 80, required), `description` (String 500, nullable), `color` (String 16, default `"amber"`), `icon` (String 32, default `"bookmark"`), `is_public` (Boolean, default false), `share_token` (String 32, unique, nullable), `created_at`, `updated_at` (DB timestamps, `updated_at` auto-touches on update). Relationship `items` uses `cascade="all, delete-orphan"`.
- **`collection_items`** (`CollectionItem`): `id`, `collection_id` (FK → `collections.id`), `anime_id` (FK → `anime.id`), `note` (String 500, nullable), `added_at`. Unique constraint `uq_collection_anime` on `(collection_id, anime_id)` prevents duplicates at the DB level. `to_dict()` embeds the full anime summary (`anime.to_dict(include_community=False)`).

Client state: TanStack Query caches under keys `["collections"]`, `["collection", id]`, and `["collection-share", token]`.

### Configuration

None specific to collections. The share-token length is the `length: int = 16` default parameter of `generate_share_token` in `utils/tokens.py`, not an env var. The API base URL (`VITE_API_URL`) applies app-wide.

### Edge cases & limits

- **Share links are currently dead-ends in the SPA.** `ShareButton` copies `/collections/share/{token}`, but `frontend/src/routes.tsx` defines no matching route — the catch-all `*` redirects to `/`. The backend endpoint and the frontend plumbing (`useSharedCollection`, `api.getSharedCollection`) exist but no routed page consumes them. A recipient who opens a share link lands on the landing page.
- **`owner` is never populated.** `CollectionDetail.owner` is typed on the frontend and `CollectionDetailPage` renders a "by {owner}" label from it, but no backend serializer emits an `owner` field, so the label never appears.
- **The detail page is effectively owner-only.** `GET /api/collections/<id>` 404s for non-owners, so the non-owner branches in `CollectionDetailPage` (hidden Edit/Delete, "Nothing here yet" copy) are unreachable through that route today.
- **No item ordering or notes UI.** `CollectionItem.position` exists in the frontend type but not in the model; items come back in default (insertion) order with no reordering. The API accepts a `note` (truncated to 500 chars) on add, but no UI sends or displays it.
- **`color`/`icon` are write-only via API.** The PATCH/POST endpoints accept them (truncated to 16/32 chars, defaulting to `amber`/`bookmark`), and `CollectionCard` uses `color` for its gradient — but `CollectionForm` never sends either, so all UI-created collections render the amber fallback and `icon` is unused everywhere.
- **Idempotency**: re-adding an existing anime returns 200 with the existing item (the unique constraint is never hit in practice); removing an absent item returns 204.
- **Validation**: missing/blank or >80-char `name` → 400; non-integer `anime_id` → 400; unknown `anime_id` → 404; `description` and `note` are silently truncated to 500 chars rather than rejected.
- **Revoked links never resurrect**: toggling public off→on issues a brand-new token; previously shared URLs 404 permanently.
- **No pagination or caps**: a user can create unlimited collections with unlimited items; the list endpoint returns everything, and `items_count` runs one `COUNT` query per collection row.
- **No rate limiting** on the unauthenticated `/api/collections/public/<token>` endpoint; token unguessability (16 URL-safe chars) is the only protection.
- **Fragile auto-add**: `AddToCollection`'s create-then-add relies on a 60 ms `setTimeout` plus a DOM query for the freshly rendered row; if the query cache hasn't refreshed in time, the new collection is created but the anime is not added.

---

## Ratings & Reviews

Ratings & Reviews is Bingery's core community-data feature: signed-in users score an anime 1–10, optionally attach a short text review, and vote on "fan genres" — a crowd-sourced tag layer (Isekai, Tearjerker, Dark Fantasy, …) that sits alongside the official genres synced from AniList. Individual ratings are aggregated into a per-anime community score and rating count, and fan-genre votes are tallied into ranked bars on the detail page.

Beyond the detail page, this data is the substrate for most other features: the recommendation engine builds taste profiles from ratings (`routes/recommend.py`, `routes/rec_signals.py`), the stats dashboard computes score distributions and per-genre averages (`routes/stats.py`), the activity feed emits rating and genre-vote events (`routes/activity.py`), the compare view shows the caller's score/review side by side (`routes/compare.py`), and the AI chatbot reads the user's top-rated titles for context (`routes/chatbot_tools.py`).

### User flow

1. User opens an anime detail page (`/anime/:id`). Community fan-genre bars and community score are visible to everyone; the "Your rating" panel shows "Sign in to rate, review, and vote on fan-genres." for anonymous visitors.
2. A signed-in user sees the rating panel pre-filled with their existing score, review text, and genre votes (the detail endpoint includes `user_rating` and `user_genre_votes` when a JWT is present).
3. They pick a score by clicking one of 10 stars (hover previews the value, a `n/10` label updates live), optionally type a review, and toggle fan-genre chips (capped at 15, with a live `n/15` counter).
4. Clicking **Save rating** (disabled until score ≥ 1) sends one combined `POST /api/anime/<id>/review`. The button flashes "Saved" for ~1.8 s; errors render inline next to the button.
5. Side effect: rating an anime auto-manages the watchlist — a missing entry is created with status `completed`, and an existing `plan_to_watch` entry is upgraded to `completed`.
6. The detail query is invalidated, so community score, rating count, and fan-genre bars refresh immediately. The rated score and assigned genres also appear later on the user's watchlist cards, stats dashboard, and activity feed.

### Frontend

- `frontend/src/routes.tsx` — route `anime/:id` renders `AnimeDetailPage`.
- `frontend/src/features/details/AnimeDetailPage.tsx` — composes the page: `FanGenreBars` inside a "Community fan genres" `GlassCard` (left column) and `RatingPanel` inside a "Your rating" card (right aside).
- `frontend/src/features/details/RatingPanel.tsx` — the whole editing surface: `StarRating`, review `<textarea>`, fan-genre chip toggles (client-side 15-cap in its `toggle` handler), save button with saved/error states. Re-seeds local state from `anime.user_rating` / `anime.user_genre_votes` when the anime id changes.
- `frontend/src/design/StarRating.tsx` — 10-star widget with hover preview, `readOnly` mode, and `aria-label`s per star.
- `frontend/src/features/details/FanGenreBars.tsx` — horizontal bars; widths are scaled relative to the top tag's vote count, colored via `genreColor`.
- `frontend/src/hooks/useRatings.ts` — `useSubmitReview(animeId)` TanStack Query mutation; on success invalidates `["anime-detail", animeId]`.
- `frontend/src/lib/api.ts` — `submitReview(id, { score, review?, genres? })` → `POST /api/anime/<id>/review`. Also defines `getMyRatings()` (see Edge cases — currently broken/unused).
- `frontend/src/lib/genres.ts` — `FAN_GENRES` (a mirror of the backend allowlist, with a comment requiring it stay in sync) and `genreColor()` (hand-picked colors plus a deterministic name-hash fallback).
- Consumers elsewhere: `frontend/src/features/discover/AnimeCard.tsx` displays `community_score ?? api_score`; `frontend/src/features/discover/FilterBar.tsx` offers a "Community score" sort option; `frontend/src/features/watchlist/WatchlistCard.tsx` shows the user's score and assigned fan-genres (delivered inline in the watchlist payload).

### Backend

All endpoints live in `routes/ratings.py` (blueprint prefix `/api`); the detail read path is in `routes/anime.py`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/anime/<id>/rate` | JWT | Upsert a 1–10 score (and review if the `review` key is present); auto-sets watchlist to `completed`. |
| DELETE | `/api/anime/<id>/rate` | JWT | Delete the caller's rating (404 if none). Returns refreshed community score/count. |
| POST | `/api/anime/<id>/review` | JWT | Combined upsert: score + optional review + optional genre-vote replacement + optional `watch_status` override. The only write path the frontend uses. |
| POST | `/api/anime/<id>/fan-genres` | JWT | Replace **all** of the caller's genre votes for this anime with the submitted list. |
| GET | `/api/anime/<id>/fan-genres` | Public | Aggregated fan-genre tallies for an anime. |
| GET | `/api/fan-genres/allowed` | Public | Full genre allowlist, both grouped (`standard`/`demographic`/`thematic`/`tone`/`setting`) and flat (`all`). |
| GET | `/api/users/<id>/ratings` | Public | Paginated list of any user's ratings — score, review text, timestamps, and embedded anime — newest-updated first. |
| GET | `/api/me/ratings` | JWT | Shortcut that delegates to the route above for the caller. |
| GET | `/api/anime/<id>` | Public (optional JWT) | Detail payload with `community_score`, `rating_count`, `fan_genres`; adds `user_rating` and `user_genre_votes` when a valid JWT is supplied. |

Notable server-side logic:

- **Non-destructive partial updates.** Both write endpoints only touch `review` when the key is present in the JSON body, so a score-only re-rate can't wipe an existing review; `/review` likewise only replaces genre votes when `genres` is present. Covered by `tests/test_ratings.py`.
- **Genre-vote replacement semantics.** Votes are delete-then-insert per (user, anime); there is no per-tag toggle endpoint.
- **Validation asymmetry.** `POST /fan-genres` rejects unknown tags with 400 and echoes the allowlist; `POST /review` validates only shape/length with 400 and **silently filters** unknown tags.
- **Watchlist coupling.** Both write paths upsert a `WatchlistEntry`: created as `completed` (or the `watch_status` override on `/review` — `watching`/`completed`/`dropped`/`on_hold` on create, those plus `plan_to_watch` on update), and an existing `plan_to_watch` entry is promoted to `completed`. The shipped frontend never sends `watch_status`; it is API-only.
- **Aggregation** lives on the `Anime` model (`models.py`): `get_community_score()` (AVG rounded to 1 decimal, `None` with no ratings), `get_rating_count()`, and `get_fan_genres()` (per-tag counts plus `percentage` = votes ÷ distinct voters on that anime × 100, sorted descending). Computed live on every request — no caching, no background jobs, no external APIs.

### Data model

Defined in `models.py`:

- **`rating`** — `id`, `user_id` (FK, indexed), `anime_id` (FK, indexed), `score` (int, `CHECK score >= 1 AND score <= 10`), `review` (Text, nullable), `created_at`, `updated_at`. Unique constraint `(user_id, anime_id)` — one rating per user per anime.
- **`fan_genre_vote`** — `id`, `user_id` (FK, indexed), `anime_id` (FK, indexed), `genre_tag` (String(60), indexed), `created_at`. Unique constraint `(user_id, anime_id, genre_tag)`.
- Depends on **`watchlist_entry`** for the auto-complete side effect, and `WatchlistEntry.to_dict(include_anime=True)` queries back into `rating`/`fan_genre_vote` to embed `score` and `genres` in watchlist payloads.
- Client state: TanStack Query cache key `["anime-detail", id]` carries `user_rating`, `user_genre_votes`, `community_score`, `rating_count`, `fan_genres`; `RatingPanel` keeps transient local `useState` for score/review/chips until save.

### Configuration

No environment variables. Tunables are hard-coded constants:

- `ALLOWED_FAN_GENRES` in `routes/ratings.py` (~70 tags) — the server-side allowlist, mirrored manually by `FAN_GENRES` in `frontend/src/lib/genres.ts`. The two lists must be kept in sync by hand.
- Genre votes per user per anime: max **15** (enforced server-side with 400, and client-side in the chip toggle).
- Review length: truncated (not rejected) to **2000** characters server-side.
- `GET /users/<id>/ratings`: `per_page` default **50**, capped at **100**.

### Edge cases & limits

- **Ratings are fully public.** `GET /api/users/<id>/ratings` requires no auth and returns scores **and review text** for any user id, with no privacy flag or opt-out. Aggregated community data on the detail page is also public; the activity feed, by contrast, is private (JWT, own events only).
- **Score validation is strict**: must be a JSON integer 1–10; floats, strings, and out-of-range values get 400. The frontend additionally disables save at score 0, which means genre votes cannot be submitted through the UI without also setting a score (the standalone `/fan-genres` POST exists but no frontend code calls it).
- **Review truncation is silent** — text beyond 2000 chars is dropped server-side with no error or client-side counter.
- **There is no way to clear a review from the UI** short of saving an empty string, and no UI calls `DELETE /api/anime/<id>/rate`; rating deletion is API-only.
- **`/review` silently discards invalid genre tags** rather than erroring, so a stale frontend list would lose votes without feedback. Duplicate tags in one payload are not deduplicated and would trip the `(user, anime, genre_tag)` unique constraint at commit.
- **"Community score" sort is a no-op.** `FilterBar` offers `sort=community_score`, but the sort map in `routes/anime.py:list_anime` only knows `api_score`/`year`/`title`/`episodes` and silently falls back to `api_score`.
- **`api.getMyRatings()` is dead and mismatched** — it requests `/ratings/me` while the backend exposes `/api/me/ratings`; nothing in the frontend calls it, so the user-facing "my ratings" listing effectively doesn't exist (watchlist cards and stats fill that role).
- **Grouped allowlist is lossy.** `/api/fan-genres/allowed` filters its group lists against `ALLOWED_FAN_GENRES`, but some group entries ("Coming of Age", "Workplace", "Urban", …) aren't in the allowlist and the "additional broad tags" block (Iyashikei, Idol, Yuri, …) belongs to no group — those tags appear only in the flat `all` array.
- **No rate limiting or moderation** on ratings, reviews, or votes; reviews are stored and served verbatim.
- **Performance note:** community score, count, and fan-genre tallies are recomputed per request, and `to_dict(include_community=True)` is the default — the paginated `/api/anime` list runs these aggregate queries per row.
- Fan-genre `percentage` cannot exceed 100 (each user votes a tag at most once), and `FanGenreBars` scales bars to the top tag's count, not the percentage.

---

## Compare, Stats & Activity Feed

Three sibling "insight" features that read the user's accumulated data (ratings, fan-genre votes, watchlist entries, collections, dub reports) and present it back: **Compare** puts two anime side-by-side with the caller's own take on each (an older user-vs-user taste comparison endpoint also exists but is no longer wired to the UI), **Stats** is a personal dashboard of aggregate numbers and charts, and **Activity** is a paginated reverse-chronological feed of everything the user has done in the app. None of the three writes data — they are pure read views over tables owned by other features.

All three are top-level navigation destinations (`Stats`, `Activity`, `Compare` in `frontend/src/layout/NavBar.tsx` and the mobile `frontend/src/layout/MoreSheet.tsx`) and all three require a logged-in user.

### User flow

#### Compare
1. User opens `/compare`. If signed out, a "Sign in to compare anime" prompt is shown instead of the tool.
2. Two `AnimePicker` inputs ("Anime A", "Anime B") each offer debounced autocomplete search (min 2 chars, 250 ms delay, top 8 results). Picking a result collapses the picker into a compact card with an ✕ button to swap the selection.
3. Nothing is fetched until **both** sides are picked; then `GET /api/compare?a=&b=` runs and renders two side cards (poster, year/episodes, public + community score, studio, genre badges, "Your take" with the caller's score and review) plus an "Overlap" panel: genre-match percentage, shared genres (amber badges), A-only / B-only genres, and a "Same studio" line when applicable.
4. Shared genres are highlighted amber on both side cards; clicking a side card navigates to `/anime/:id`.

#### Stats
1. User opens `/stats` (signed-out users get a sign-in prompt).
2. Two queries fire in parallel: `/api/stats/overview` and `/api/stats/heatmap`. Skeletons render until each resolves.
3. The page shows six overview cards (Ratings, Completed, Hours watched, Favorites, Avg rating, Streak in days), a 10-bucket rating histogram, a top-genres bar list, and a GitHub-style 365-day activity heatmap (hover a cell for `date — count`).

#### Activity
1. User opens `/activity` (signed-out users get a sign-in prompt).
2. `GET /api/activity?page=1` loads the first 50 events, newest first. Each row shows the anime poster (when the event has one), a human label ("Rated X · 8/10", "completed · X", "Favorited X", "Added X to collection", "Started a new collection — Name", "Voted Isekai on X", "Reported dub date for X ep 5 · pending review"), and a localized timestamp.
3. Rows with an associated anime link to `/anime/:id`. If more than one page exists, Prev/Next buttons with a `page / pages` indicator drive pagination (client keeps the page number in local state and refetches).

### Frontend

Routes are lazy-loaded in `frontend/src/routes.tsx`: `stats` → `StatsPage`, `activity` → `ActivityPage`, `compare` → `ComparePage`. All three pages read `useAuth` (`frontend/src/stores/auth.ts`) and disable their queries (`enabled: !!user`) when signed out.

#### Compare
- `frontend/src/features/compare/ComparePage.tsx` — holds `a`/`b` picks as local `AnimeSummary | null` state; renders skeletons while fetching, an error line on failure.
- `frontend/src/features/compare/AnimePicker.tsx` — self-contained search-and-pick widget built on `useSearch` (`frontend/src/hooks/useSearch.ts`, which calls `api.autocomplete`); closes its dropdown on outside click.
- `frontend/src/features/compare/CompareSummary.tsx` — the two `Side` cards plus the Overlap panel; computes the genre-match percentage client-side as `shared / (shared + aOnly + bOnly) * 100`.
- `frontend/src/hooks/useCompare.ts` — React Query, key `["compare", aId, bId]`, `enabled` only when both ids are non-null, `staleTime: 60_000`.
- `api.compareAnime(aId, bId)` in `frontend/src/lib/api.ts` → `GET /compare?a=&b=`. A code comment there records that the user-vs-user path was dropped from the UI because the deployment has a single demo user.

#### Stats
- `frontend/src/features/stats/StatsPage.tsx` — composes the four widgets below.
- `frontend/src/features/stats/OverviewCards.tsx` — six metric cards; hours are rounded to an integer, avg rating formatted `x.x/10` (em dash when null).
- `frontend/src/features/stats/RatingHistogram.tsx` — always renders bars for scores 1–10; bar height is relative to the max bucket with a 2% floor so empty buckets stay visible.
- `frontend/src/features/stats/GenreBreakdown.tsx` — top 8 genres as horizontal bars, colored via `genreColor` from `frontend/src/lib/genres`.
- `frontend/src/features/stats/ActivityHeatmap.tsx` — rebuilds the full 365-day grid client-side (server only sends non-zero cells), padded back to the previous Sunday and laid out as week columns; cell intensity is amber with alpha `0.18 + (count/max) * 0.72`.
- `frontend/src/hooks/useStats.ts` — `useStatsOverview` / `useStatsHeatmap`, keys `["stats-overview"]` / `["stats-heatmap"]`, both `staleTime: 60_000`.

#### Activity
- `frontend/src/features/activity/ActivityPage.tsx` — page number in `useState`, Prev/Next `Button`s disabled at the bounds, 10 skeleton rows while loading, "No activity yet." empty state.
- `frontend/src/features/activity/ActivityEntry.tsx` — maps each `ActivityEvent.kind` to a label string; wraps the row in a `Link` to the anime page when `event.anime.id` exists.
- `frontend/src/hooks/useActivity.ts` — key `["activity", page]`, no `staleTime`. The client always uses the server defaults (`limit=50`, no `before`).

Response/type shapes (`StatsOverview`, `StatsHeatmap`, `ActivityEvent`, `ActivityResponse`, `AnimeCompareResponse`, etc.) live in `frontend/src/types/models.ts` with thin `*Resp` aliases in `frontend/src/types/api.ts`.

### Backend

Blueprints registered in `app.py`: `compare_bp` at `/api/compare`, `stats_bp` at `/api/stats`, `activity_bp` at `/api/activity`. Every endpoint is `@jwt_required()`; identity comes from the JWT (`get_jwt_identity()`), so each user sees only their own data (except `/compare/users`, which compares any two named users).

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/compare?a=<anime_id>&b=<anime_id>` | JWT | Anime-vs-anime: both anime payloads (with community data), the caller's rating/review/fan-genre votes per side, shared/unique official genres, shared fan genres, shared studio. 400 if `a`/`b` missing or non-integer, 404 if either anime is unknown. |
| GET | `/api/compare/users?user_a=<username>&user_b=<username>` | JWT | User-vs-user taste comparison: top shared / A-only / B-only fan-genre slices (max 8 each), up to 24 shared rated anime, and a 0–1 `score_agreement`. 400 if a username is missing, 404 if a user is unknown. Any logged-in caller may compare any two users. **Not called by the current frontend.** |
| GET | `/api/stats` | JWT | Legacy full dashboard: totals (rated, genre votes, average score), year distribution, score distribution (1–10), top 10 studios, top 15 fan tags, estimated hours watched. **Not called by the current frontend.** |
| GET | `/api/stats/genres` | JWT | Per fan-genre breakdown: count, `avg_score` (unrated votes count as 0), `weighted_score = avg × count`; sorted by weighted score desc, name asc. **Not called by the current frontend.** |
| GET | `/api/stats/timeline` | JWT | Rated-anime count and average score grouped by anime release year (null years excluded). **Not called by the current frontend.** |
| GET | `/api/stats/overview` | JWT | Powers the Stats page: overview block (`total_rated`, `total_watched`, `hours_watched`, `favorite_count`, `avg_rating`, `top_genre`, `streak_days`), 10-bucket `rating_distribution`, `top_genres` (max 8). |
| GET | `/api/stats/heatmap` | JWT | Powers the heatmap: non-zero per-UTC-day activity counts for the last 365 days (inclusive) plus the window max. |
| GET | `/api/activity?page=&limit=&before=` | JWT | Paginated unified event feed, newest first. `limit` defaults to 50, clamped to 1–200; `page` defaults to 1 (min 1); optional `before` is an ISO-8601 cursor (tz-aware or naive) — 400 on an unparseable value. Returns `{events, page, pages}`. |
| GET | `/api/activity/on-this-day` | JWT | Events whose timestamp matches today's month/day in a **previous** year (UTC). Returns `{items}`. **Not called by the current frontend.** |

#### Notable server-side logic
- **Compare (anime)** — `routes/compare.py:_side_payload` builds each side from `Anime.to_dict(include_community=True)` (which computes `community_score`, `rating_count`, and aggregated `fan_genres` live via SQL) plus the caller's `Rating` and `FanGenreVote` rows. `shared.fan_genres` is the intersection of *the caller's own* votes on the two anime, not community votes. `shared.studios` is a one-element list only when both studios are equal and non-null.
- **Compare (users)** — `score_agreement = 1 − mean(|score_a − score_b|) / 9` over commonly rated anime, clamped to [0, 1] and rounded to 2 decimals; no shared ratings gives 0.0 (1.0 for self-compare). Self-compare treats every genre as shared with its count doubled (the general rule is shared count = a + b). Shared anime are ordered by the more recent `updated_at` of the rating pair and capped at 24, serialized with `include_community=False`.
- **Hours-watched estimate** (used identically by `/stats` and `/stats/overview`) — derived from the watchlist, not ratings: a `watching` entry with `episodes_watched > 0` contributes `episodes_watched × 24` minutes; otherwise `anime.episodes × 24 × weight` where weight is `completed` 1.0, `watching`/`on_hold` 0.5, `dropped` 0.25, `plan_to_watch` 0.0.
- **Activity dates** (streak + heatmap) — `routes/stats.py:_activity_dates_for_user` counts `Rating.created_at`, `FanGenreVote.created_at`, and `WatchlistEntry.updated_at` per UTC calendar date (naive datetimes are treated as UTC). The streak counts consecutive active days ending **today** (UTC); a day without activity yet means streak 0.
- **Activity feed synthesis** — `routes/activity.py:_fetch_events` runs six queries (ratings, genre votes, watchlist entries, collection items, collections, dub reports) and synthesizes seven event kinds in Python. A `favorite` event is emitted alongside `watch_status` whenever `is_favorite` is true. Event ids are globally unique synthetics: `KIND_CODE[kind] × 10¹² + row_pk` (codes 1–7). Sorting is a stable two-pass Python sort — ascending `kind` as tiebreak, then descending timestamp — and pagination is list slicing after the optional `before` filter. There is no DB-level pagination, caching, external API, or background job in any of the three features.

### Data model

These features own no tables; everything is read-only over models in `models.py`:

- **`Rating`** — `user_id`, `anime_id`, `score` (int, CHECK 1–10), `review` (nullable text), `created_at`, `updated_at`; unique `(user_id, anime_id)`. Used by all three features.
- **`FanGenreVote`** — `user_id`, `anime_id`, `genre_tag` (string 60), `created_at`; unique `(user_id, anime_id, genre_tag)`. Drives genre slices, compare overlap, activity `genre_vote` events.
- **`WatchlistEntry`** — `status`, `episodes_watched`, `is_favorite`, `created_at`, `updated_at`. Drives hours-watched, totals, streak/heatmap, and `watch_status`/`favorite` events.
- **`Collection`** (`name`, `created_at`) and **`CollectionItem`** (`added_at`) — `collection_create` / `collection_item` events.
- **`DubReport`** (`submitted_by`, `air_date`, `status`, `note`, `created_at`) joined through **`Episode`** (`episode_number`) — `dub_report` events.
- **`Anime`** — titles, `year`, `episodes`, `studio`, `api_score`, `image_url`, `official_genres` (via `to_dict`); plus computed `community_score`/`fan_genres` for compare sides.
- **`User`** — `username`, `display_name` for `/compare/users` lookups.

Client state: React Query caches keyed `["compare", aId, bId]`, `["stats-overview"]`, `["stats-heatmap"]`, `["activity", page]`; the only local UI state is the two picker selections (Compare) and the page number (Activity).

### Configuration

No environment variables. Tuning lives in module constants:

- `routes/stats.py` — `DEFAULT_EPISODE_MINUTES = 24`; `COMPLETION_WEIGHTS = {completed: 1.0, watching: 0.5, on_hold: 0.5, dropped: 0.25, plan_to_watch: 0.0}`; heatmap window `today − 364` days (365 inclusive).
- `routes/activity.py` — `KIND_CODE` (rating 1 … dub_report 7), `_ID_OFFSET = 10**12`; feed `limit` default 50, max 200.
- `routes/compare.py` — genre slice cap 8 (`_slice_sorted_top`), shared-anime cap 24.
- Frontend — compare/stats queries use `staleTime: 60_000` ms; `AnimePicker` search debounce 250 ms, min 2 chars, 8 results shown.

### Edge cases & limits

- **Activity feed is O(all events) per request.** Every query loads the user's complete history into memory before sorting and slicing; `page`/`limit`/`before` only change the slice, not the work. Fine at hobby scale, a known scaling constraint.
- **The feed reflects current row state, not an append-only log.** `rating` and `watch_status` events use `updated_at`, so editing a rating or watchlist entry moves the event to "now" — the older occurrence disappears. A `favorite` event shares its row's `updated_at`, so its timestamp reflects the entry's last update, not when it was favorited; unfavoriting removes the event entirely. Similarly there is exactly one `watch_status` event per entry (latest status only).
- **Synthetic event ids** are collision-free only while per-table primary keys stay below 10¹². Events whose timestamp is `NULL` are silently dropped from the feed.
- **Pagination quirks**: requesting a `page` beyond `pages` returns an empty `events` array with `pages` unchanged (the UI prevents this by disabling Next). `pages` is `max(1, ceil(total/limit))`, so an empty feed still reports `pages: 1`. An invalid `limit`/`page` silently falls back to defaults; only an invalid `before` produces a 400.
- **Streak resets at UTC midnight**: the streak requires activity *today* in UTC — a user who was active yesterday but not yet today sees `streak_days: 0`. Heatmap buckets are also UTC dates, while `ActivityHeatmap.tsx` builds its grid from the browser's local calendar, so day alignment can be off by one for users far from UTC.
- **Hours watched is an estimate**: a flat 24 minutes per episode regardless of real runtime; anime with `episodes = NULL` contribute 0 unless they are `watching` with tracked progress; `plan_to_watch` contributes nothing; a rating alone implies no watch time.
- **`/stats/genres` averaging**: votes on unrated anime contribute a score of 0 to the average (deliberately, so `weighted_score = avg × count` isn't inflated), which drags `avg_score` down for genres with many unrated votes.
- **Compare**: the query is disabled until both anime are chosen, so there are no partial fetches; results are cached 60 s per id pair. The genre-match percentage shown in the UI considers official genres only. 404 if either id is unknown; comparing an anime to itself is allowed (100% overlap).
- **`/compare/users`** allows self-compare (agreement 1.0, shared genre counts doubled) and lets any authenticated user inspect any other user's taste profile by username. It and `/api/stats` (dashboard), `/api/stats/genres`, `/api/stats/timeline`, `/api/activity/on-this-day` are live, tested endpoints with **no current frontend callers** — kept server-side after the UI consolidated on `/compare?a=&b=`, `/stats/overview`, `/stats/heatmap`, and `/activity`.
- No rate limiting, caching layers, or external API calls in any of the three features; all data is first-party SQL. Missing/expired JWTs get the standard flask-jwt-extended 401.

---

## For You — Recommendations

The For You page (`/for-you`) is a personalized anime feed built from the user's own activity: ratings, fan-genre votes, and watchlist statuses. It exists to replace generic "most popular" discovery with picks grounded in measurable per-user signals (studio hit-rate, genre weights, era lean, episode-length preference, etc.) and to show the user *why* each pick was made via a one-line reason.

The ranking math lives in a shared multi-signal scorer (`routes/rec_signals.py`) that is deliberately reused by the AI chat's recommend mode (see `docs/superpowers/specs/2026-05-21-chat-rec-engine-design.md`), so the For You page and chat recommendations rank with identical numbers. The For You page itself involves **no LLM call** — it is pure SQL + Python scoring. AI enters only on the chat side, where the same scored candidate set is handed to the LLM as grounding context (`routes/chat_context.py`) and the LLM's picks are validated against it (`routes/chatbot.py`).

### User flow

1. Signed out: visiting `/for-you` shows a "Sign in to see your picks" prompt; no API call is made (the query is disabled).
2. New signed-in user with zero ratings: the backend returns a "popular" fallback feed (top `api_score` anime) with the fixed reason "Popular and highly rated — a good starting point." No taste card is shown.
3. The user rates anime (1–10), votes on fan genres, and sets watchlist statuses elsewhere in the app. These are the only signal inputs — there is no like/dismiss button on recommendations.
4. On the next visit, the page shows:
   - a **"Your taste"** card (`TasteProfile`): up to 8 genre bars with percentage weights, total rating count, and average score;
   - a **"Picks for tonight"** grid of up to 20 recommended anime;
   - up to 6 glass cards repeating the top picks with their per-pick reason text (e.g. "matches your top studio (MAPPA)", "underrated pick outside the top-100").
5. Results are cached client-side for 5 minutes (React Query `staleTime`); server-side, the signal profile recomputes lazily whenever the user's rating count changes.

### Frontend

- `frontend/src/features/for-you/ForYouPage.tsx` — page component, lazy-loaded at path `for-you` in `frontend/src/routes.tsx`. Gates on `useAuth` (`frontend/src/stores/auth`); renders the taste card, the grid, and the reason cards.
- `frontend/src/features/for-you/TasteProfile.tsx` — renders `top_genres` as horizontal bars (width = `weight * 100`%, min 6%), colored via `genreColor` from `frontend/src/lib/genres`. Returns `null` when the profile is absent or has no genres.
- `frontend/src/hooks/useRecommendations.ts` — React Query hook, `queryKey: ["recommendations"]`, `staleTime: 5 * 60_000`, `enabled` only when a user is logged in.
- `frontend/src/lib/api.ts` — `getRecs()` calls `GET /recommend/for-me`. `/recommend` is in `NSFW_AWARE_PREFIXES`, so when the global NSFW toggle (`frontend/src/stores/nsfw`) is on, `?include_nsfw=true` is appended automatically.
- Composition reuse: `AnimeGrid` from `frontend/src/features/discover/AnimeGrid` and `GlassCard` from `frontend/src/design/GlassCard`.
- Navigation: "For you" links in `frontend/src/layout/NavBar.tsx` (desktop) and `frontend/src/layout/BottomTabBar.tsx` (mobile, Sparkles icon).
- Types: `Recommendation` and `TasteProfile` in `frontend/src/types/models.ts`; `RecommendationsResponse` in `frontend/src/types/api.ts`.

### Backend

Blueprint `recommend_bp` (`routes/recommend.py`), prefix `/api/recommend`, registered in `app.py`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/recommend/for-me?limit=20` | JWT | Personalized recommendations (or popular fallback for unrated users). Returns `{recommendations: [{anime, reason, relevance_score}], taste_profile, source}` |
| GET | `/api/recommend/taste-profile` | JWT | Just the serialized taste profile (`{profile}` or `{profile: null}`) |
| GET | `/api/recommend/similar/<anime_id>?limit=8` | None | Anime similar to a given one, by official + fan genre-tag overlap. 404 if the anime id is unknown |
| GET | `/api/recommend/onboarding` | None | Curated set: top-rated anime, one per each of 10 major genres, for new users to rate |

#### Recommendation pipeline (`/for-me`)

1. `build_taste_profile(user_id)` (legacy profile in `routes/recommend.py`) checks whether the user has any ratings. No ratings → popular fallback (`source: "popular"`, `taste_profile: null`, `relevance_score: null`).
2. Otherwise it defers to the multi-signal engine in `routes/rec_signals.py`:
   - `get_signal_profile(user_id)` — lazy-cached profile fetch (see Data model).
   - `score_candidates(user_id, profile, limit, include_nsfw=False)` — scores every unwatched anime and returns the top N.
3. Each pick's `reason` string is derived in `_reason_for`: the highest weighted contribution among studio affinity (25×), genre match (20×), fan-genre match (15×), surprise factor (10×), and watchlist alignment (5×) wins; if none contribute, it falls back to "`NN`% match with your overall taste."
4. `relevance_score` = `total_score / 100` (0–1 float).

#### Scoring formula (`score_candidate`, per candidate, clamped to [0, 100])

```
total = 25·studio_affinity + 20·genre_match + 15·fan_genre_match
      + 10·era_fit + 10·episode_fit + 10·surprise_bonus
      + 5·watchlist_coherence − 20·dropped_trait_penalty
```

- `studio_affinity` — user's hit-rate for the candidate's studio (`hit_rate` = share of that studio's ratings ≥ 8; only studios with ≥ 2 ratings qualify, top 5 kept).
- `genre_match` / `fan_genre_match` — weighted-Jaccard share of the user's genre weights (official genres weighted by `max(0, score − 5)`, top 8) / fan-genre vote counts that the candidate covers.
- `era_fit` — Gaussian around the user's rating-weighted average release year, σ = 6 years; 0 when either year is unknown.
- `episode_fit` — user's share for the candidate's bucket: short ≤ 13 eps, medium 14–26, long > 26, computed from completed watchlist entries (fallback: anime rated ≥ 6).
- `surprise_bonus` — 1.0 if `api_score ≥ 8` AND outside the top-100 by `Anime.popularity`; 0.5 if exactly one holds.
- `watchlist_coherence` — 1 if the candidate is in the user's "planning" watchlist (see Edge cases — effectively dead).
- `dropped_trait_penalty` — up to 0.5 for studio match plus up to 0.5 for genre share against the studios/genres of anime the user rated ≤ 5 or dropped.

Hard exclusions before scoring: anything the user has rated (any score) or has in the watchlist with status `watching` / `completed` / `dropped` / `on_hold`. NSFW: hard-blocked genres (Hentai) always filtered; soft-blocked (Ecchi) filtered unless the request opts in (`utils/nsfw.py`).

#### AI involvement

The For You endpoint is fully deterministic. The same engine grounds the AI chat: `routes/chat_context.py::build_llm_context` attaches the top 40 scored candidates (80 in the zero-rating cold-start case) to the LLM context when chat mode is `recommend`, and `routes/chatbot.py` filters the LLM's `suggested_anime` down to ids present in that candidate set, silently dropping hallucinated titles.

### Data model

- **`User.taste_profile_cache`** (`models.py`, `TEXT`, nullable) — the only column this feature owns. Stores the JSON signal profile: `schema_version`, `computed_at`, `rating_count_at_compute`, `top_genres`, `top_studios`, `fan_genre_clusters`, `era_lean_year`, `episode_fit_pref`, `dropped_traits`, `loved_examples` (max 5), `dropped_or_low_examples` (max 3), `currently_watching` (max 3), `watchlist_planning_ids` (max 20). Lazy invalidation in `get_signal_profile`: recompute and rewrite when the cache is missing/unparseable, the stored `schema_version` ≠ `SIGNAL_PROFILE_SCHEMA_VERSION`, or the user's current rating count differs from `rating_count_at_compute`.
- **Read dependencies:** `Rating`, `FanGenreVote`, `WatchlistEntry`, `Anime` (`studio`, `year`, `episodes`, `api_score`, `popularity`), `Genre` / `anime_genres`, plus the `Anime.get_fan_genres()` and `Anime.get_community_score()` aggregates.
- **Client state:** React Query cache under key `["recommendations"]`; no Zustand store of its own (reads `useAuth` and `useNsfw`).
- There is **no recommendation-feedback table** (no likes, dismissals, or impressions are persisted).

### Configuration

No dedicated environment variables. Tuning constants in code:

- `SIGNAL_PROFILE_SCHEMA_VERSION = 1` (`routes/rec_signals.py`) — bump to force profile recompute for all users.
- Signal weights `25/20/15/10/10/10/5/−20` and era σ = 6 years — hard-coded in `score_candidate` / `_era_fit`.
- Episode buckets: short ≤ 13, medium ≤ 26, long > 26; studio qualification `n ≥ 2`; "hit" threshold score ≥ 8; genre weight `max(0, score − 5)`.
- `_RECOMMEND_LIMIT = 40`, `_RECOMMEND_LIMIT_COLD = 80` (`routes/chat_context.py`, chat path only).
- `/for-me` `limit` default 20, capped at 50; `/similar` default 8, capped at 20.
- NSFW lists: `HARD_BLOCKED_GENRES = ("Hentai",)`, `SOFT_BLOCKED_GENRES = ("Ecchi",)` (`utils/nsfw.py`).
- Frontend: `staleTime` 5 minutes (`useRecommendations.ts`).

### Edge cases & limits

- **No explicit feedback signals.** Despite the engine's name, there are no like/dismiss endpoints or UI anywhere in the code — signal collection is entirely implicit (ratings, fan-genre votes, watchlist status changes). The spec explicitly defers rejection-feedback re-scoring to a later phase (§12).
- **`"planning"` status mismatch (dead signal).** `routes/rec_signals.py` queries `WatchlistEntry.status == "planning"`, but the app only ever writes statuses from `models.WATCH_STATUSES = ["watching", "completed", "plan_to_watch", "dropped", "on_hold"]`. `watchlist_planning_ids` is therefore always empty: the +5 `watchlist_coherence` bonus and the "already in your planning list" reason never fire in practice. `plan_to_watch` entries do correctly remain in the candidate pool (only the other four statuses are excluded).
- **Cold start.** Zero ratings → popular fallback feed on For You; in chat, an empty profile is used with a larger 80-candidate set where `surprise_bonus` and genre keywords dominate.
- **NSFW nuances.** `/for-me` passes `include_nsfw=False` into `score_candidates`, but `maybe_exclude_nsfw` reads the live `?include_nsfw=true` request arg itself, so the global frontend toggle still reveals Ecchi; Hentai stays blocked. If a caller ever passed `include_nsfw=True` to `score_candidates`, *no* NSFW filter would be applied at all (the in-code comment claims Hentai stays excluded, but the code skips `maybe_exclude_nsfw` entirely) — currently no caller does. `/onboarding` applies no NSFW filtering at all.
- **Performance shape.** `score_candidates` pulls the entire unwatched catalog and scores it in Python, calling `Anime.get_fan_genres()` per candidate (an N+1 query pattern). The spec budget is < 200 ms for ~15k titles; fine at current scale but the first thing to revisit as the catalog grows.
- **Cache staleness windows.** Invalidation only fires on rating-*count* change or schema bump. Editing an existing rating's score, or any watchlist-only change, does not recompute the profile (so `episode_fit_pref`, `dropped_traits`, `top_studios` can lag until the next count change). Candidate *exclusions* are always fresh — they're queried live, not cached.
- **Two profile systems coexist.** The legacy `build_taste_profile` in `routes/recommend.py` still gates the popular-vs-personalized branch and produces the `taste_profile` JSON for the UI card; ranking is delegated to the newer signal engine. The two can disagree (e.g. top genres are computed with different weighting).
- **Frontend type drift (harmless).** `frontend/src/types/models.ts` declares `Recommendation.score`, but the backend sends `relevance_score`; the UI only reads `anime` and `reason`. `relevance_score` is `null` for the popular fallback.
- **Unused-by-UI endpoints.** The current React app never calls `/api/recommend/similar/<id>` (the details page uses `/api/anime/<id>/similar` via `SimilarStrip`) or `/api/recommend/onboarding`; both remain live, unauthenticated endpoints.
- **Chat hallucination guard.** In chat recommend mode, any LLM-suggested anime whose id isn't in the scored candidate set is silently dropped; if everything is dropped, the user just gets the text response with no cards.

---

## AI Chat Assistant

Bingery's chat assistant ("Guide" in the UI) is a conversational anime advisor backed by a pluggable LLM provider — Anthropic's API or a self-hosted Ollama instance, selected by env var. It runs in three modes (Recommend, Rate-with-AI, Onboard), each with its own mission prompt layered on a shared formatting prompt. The model can call five backend tools against the local anime database, the user's library, and the live AniList API; in authenticated Recommend mode its picks are additionally grounded against a pre-scored candidate set so it cannot recommend anime the user already engaged with.

The assistant's replies are post-processed on the server: bold `**Title**` mentions are resolved to real database rows and returned as structured anime-card refs, and `[OPTIONS: a | b | c]` markers (or heuristically detected "X or Y?" questions) become clickable answer pills. The chat itself is stateless on the server — the full conversation is round-tripped from the client on every turn.

### User flow

1. The user opens `/chat` (route is public; works logged-out with reduced personalization). A mode can be pre-selected via query string, e.g. `/chat?mode=rate`; default is `recommend`.
2. Each mode seeds the thread with a canned assistant greeting. Switching modes via the pill buttons resets the conversation to that mode's seed (deliberate — stale turns from another mode make small local models ignore the new mission prompt).
3. The user types a message (or taps a suggested pill). The frontend POSTs the message, the full conversation so far, and the mode to `/api/chat/message`, showing an animated typing indicator while waiting.
4. The backend builds the system prompt (mode mission + base prompt + user id + optionally the grounding context JSON), then runs a tool loop: the model may call tools (taste profile, watchlist, DB search, AniList search, anime details) up to 5 rounds before producing prose.
5. The final text is scanned: every `**Title**` is looked up in the local DB (exact match first, then fuzzy substring, ranked by `api_score`); resolved, non-NSFW matches come back as `suggested_anime` cards. `[OPTIONS: …]` markers become `suggested_actions`.
6. The UI renders the reply bubble (minimal markdown: bold/italic only), up to 6 anime cards linking to `/anime/:id`, and — on the latest assistant turn only — the option pills, which send their label as the next user message when tapped.
7. If the provider is unreachable, the user sees a dedicated "Taste guide is offline" banner instead of a generic error.

### Frontend

- `frontend/src/features/chat/ChatPage.tsx` — the page component. Owns the mode state (`recommend` | `rate` | `onboard`), per-mode greetings/seeds (`MODE_META`), the scrolling message list, option-pill rendering, the composer form, the typing-dots loader, and the offline banner. Contains a tiny inline `Markdown` renderer supporting only `**bold**` and `*italic*`.
- `frontend/src/features/chat/ChatAnimeCard.tsx` — compact recommendation card (poster thumb, title, year, up to 3 genre badges); links to `/anime/:id` when the ref has an id, renders un-linked otherwise.
- `frontend/src/hooks/useChat.ts` — conversation state hook. Keeps `turns` in React state, appends the user turn optimistically, calls `api.chatMessage`, attaches `suggested_anime`/`suggested_actions` as `extra` on the assistant turn, and resets the thread when the mode changes. Maps a 503 with code `provider_unavailable` to an `offline` flag.
- `frontend/src/lib/api.ts` — `api.chatMessage` POSTs to `/api/chat/message`; `ApiError.code` is populated from the response body's `stop_reason`, which is how the offline state is detected.
- `frontend/src/types/models.ts` / `frontend/src/types/api.ts` — `ChatAnimeRef`, `ChatMessage`, `ChatResponse`, `ChatRequest` types.
- Route registration: `frontend/src/routes.tsx` lazily loads `ChatPage` at path `chat` under the `AppShell` layout. There is no auth guard on the route.

There is no chat store — state lives in the `useChat` hook and is lost on refresh or mode switch.

### Backend

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/chat/message` | Optional JWT | Main chat turn: runs the tool loop, returns `response`, `suggested_anime`, `suggested_actions`, `stop_reason`. |
| GET | `/api/chat/quick-recommend` | JWT required | One-shot "recommend me one anime" reply (`response` text only). Currently unused by the frontend. |

Blueprint: `chatbot_bp` in `routes/chatbot.py`, registered in `app.py` with prefix `/api/chat`.

#### Request handling (`routes/chatbot.py`)

- Accepts `message` (required, 400 if missing), `conversation` (or legacy `history`), and `mode`. Client-supplied `system`-role messages are silently dropped — only `user`/`assistant` roles are accepted, so callers cannot inject instructions above the real system prompt.
- The system prompt is composed by `build_system_prompt(mode)` in `routes/chatbot_tools.py`: the per-mode mission (`MODE_PROMPTS`) is placed *before* the shared `BINGERY_SYSTEM` base (small local models anchor on whatever comes first). Unknown/missing modes fall back to `recommend`. For authenticated users, `[authenticated user id: N]` is appended.
- **Grounding (authenticated `recommend` mode only):** `build_llm_context` (`routes/chat_context.py`) is appended as a `# CONTEXT JSON` block. It contains the user's cached signal profile (cache-only fields stripped) and a `candidates` array of pre-scored anime — 40 normally, 80 for cold-start users with zero ratings. After generation, resolved card refs are filtered to that candidate id set, so even if the model names something outside the list it never surfaces as a card.
- **Tool loop:** up to `MAX_TOOL_LOOPS = 5` provider round-trips. Tool calls are executed by `execute_tool` in `routes/chatbot_tools.py` and fed back as `tool`-role messages. Exhausting the loop returns a friendly "ask a narrower question" reply with `stop_reason: "loop_limit"` (HTTP 200).
- **Card extraction:** the model's hallucination-prone `[ANIME_ID:N]` markers are stripped and ignored; instead each `**Title**` is resolved via `_resolve_title` (case-insensitive exact match on `title`/`title_english`, then `ilike` substring fallback, ordered by `api_score` desc). Anime tagged Hentai *or* Ecchi are unconditionally excluded from cards regardless of the user's NSFW toggle (the toggle governs list views, not chat cards).
- **Option extraction:** `_extract_options` parses the explicit `[OPTIONS: …]` marker (each choice ≤ 40 chars, max 5). Because small local models often ignore the marker instruction, `_autofill_options_from_question` heuristically extracts pills from trailing "X or Y?" / "X, Y, or Z?" questions — it only fires when it finds 2–5 clean choices (≤ 40 chars, ≤ 6 words each).

#### Tools (`utils/ai_tools.py` schemas, `routes/chatbot_tools.py` execution)

Provider-neutral `ToolSchema` definitions, single source of truth in `ALL_TOOLS`:

| Tool | What it does |
|---|---|
| `search_anime_database` | Local DB search by title substring, official genre, min `api_score`; sortable; limit clamped to 20. Returns id, scores, year, episodes, studio, truncated synopsis (300 chars), official + fan genres. |
| `get_user_taste_profile` | `build_taste_profile(user_id)` from `routes/recommend.py`: top 10 genres, avg score, total rated, preferred years. Returns an error JSON if not logged in; a "user is new" message if no ratings. |
| `get_user_watchlist` | The user's ratings ordered by score desc, limit clamped to 100 (default 50). Used to avoid duplicate recommendations. |
| `get_anime_details` | Full `Anime.to_dict(include_community=True)` by internal id. |
| `search_anilist` | Live AniList GraphQL search via `utils/anilist.AniListClient` (5 results); any exception is caught and returned as a JSON error string so the loop continues. |

All tools return JSON strings; unknown tool names return `{"error": "Unknown tool: …"}` rather than raising.

#### Provider abstraction (`utils/ai_provider.py`, `utils/ai_providers/`)

- Shared dataclasses `Message`, `ToolSchema`, `ToolCall`, `AIResponse`, an `AIProvider` Protocol with `chat()` and `stream()` methods, and a `get_provider()` factory keyed on `AI_PROVIDER`. Assistant turns carry structured `tool_calls` so each provider can round-trip them in its native wire format.
- `utils/ai_providers/anthropic_provider.py` — uses the `anthropic` SDK. Converts `tool`-role messages to `tool_result` content blocks under a `user` turn and assistant tool calls to `tool_use` blocks (required for Anthropic to accept later `tool_result`s). `APIConnectionError`, `RateLimitError`, and `InternalServerError` are mapped to `ProviderUnavailableError`.
- `utils/ai_providers/ollama_provider.py` — raw `requests` against `POST {base}/api/chat`, 120 s timeout, `num_predict` for the token cap. Supports custom headers for tunneled deployments (Cloudflare Access service tokens). Connection/timeout/chunked-encoding errors and gateway 502/503/504 responses become `ProviderUnavailableError`. **Prompt fallback:** if a tools-enabled call returns neither tool calls nor text (model lacks native function calling), it retries once with the tool schemas injected into the system prompt as JSON and instructs the model to emit a single `{"tool": …, "arguments": …}` object, which `_extract_tool_json` recovers via brace matching; synthesized call ids are prefixed `ollama_fb_`.
- `ProviderUnavailableError` is the typed "AI box is asleep / tunnel down" signal: `/api/chat/message` catches it and returns **503** with `stop_reason: "provider_unavailable"` and a friendly message instead of a 500.

#### Streaming

Both providers implement `stream()` (Anthropic via `client.messages.stream(...).text_stream`; Ollama via NDJSON line iteration with `stream: true`), but **no HTTP route currently calls it** — `/api/chat/message` is a blocking request/response and the frontend shows a typing-dots placeholder instead of streamed text. Streaming exists at the provider layer only.

#### Token budgeting

Coarse, not adaptive: every provider call uses the default `max_tokens = 2048` output cap (Anthropic `max_tokens`, Ollama `options.num_predict`). Input size is bounded indirectly — the grounding candidate list is capped at 40/80 entries, tool results clamp their own limits (20 DB rows, 100 watchlist rows, 300-char synopses), and the system prompt enforces an ~80-word reply. The full conversation history is re-sent every turn with no trimming or token counting. Providers report `usage` (input/output token counts) on `AIResponse`, but the route does not surface it to the client. (`utils/tokens.py` is unrelated — it generates URL-safe share tokens.)

### Data model

The chat feature owns no tables. Conversation history is pure client state (React state in `useChat`), discarded on refresh or mode switch and replayed to the server each turn. It depends on:

- `anime` (+ `genres`, `anime_genres`, fan-genre data) — title resolution, tool searches, candidate scoring.
- `ratings`, `watchlist_entries`, `fan_genre_votes` — taste profile and signal profile inputs.
- `users.taste_profile_cache` — JSON cache of the signal profile written by `get_signal_profile` (`routes/rec_signals.py`); lazily invalidated when `schema_version` or the user's rating count changes.

### Configuration

| Variable / constant | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `anthropic` | Selects provider: `anthropic` or `ollama` (anything else raises `ValueError`). |
| `ANTHROPIC_API_KEY` | — (required for Anthropic) | API key; constructor raises if unset. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Anthropic model id. |
| `OLLAMA_BASE_URL` (or legacy `OLLAMA_URL`) | `http://localhost:11434` | Ollama endpoint; trailing slash stripped. |
| `OLLAMA_MODEL` | `gemma4:31b` | Ollama model name. |
| `OLLAMA_EXTRA_HEADERS` | unset | JSON object of headers sent on every Ollama request; malformed JSON is silently ignored. |
| `OLLAMA_CF_ACCESS_CLIENT_ID` / `OLLAMA_CF_ACCESS_CLIENT_SECRET` | unset | Shortcut pair for Cloudflare Access service-token headers; overrides matching keys from the JSON var. |
| `OllamaProvider.timeout` | `120.0` s | Per-request HTTP timeout (constructor arg, not env-configurable). |
| `MAX_TOOL_LOOPS` (`routes/chatbot.py`) | `5` | Max provider round-trips per chat turn. |
| `max_tokens` (provider default) | `2048` | Output token cap per call. |
| `_RECOMMEND_LIMIT` / `_RECOMMEND_LIMIT_COLD` (`routes/chat_context.py`) | `40` / `80` | Grounding candidate count (cold = zero ratings at profile compute). |

### Edge cases & limits

- **Provider offline:** `/api/chat/message` returns 503 with `stop_reason: "provider_unavailable"` and a human-readable message; the UI shows the dedicated offline banner. `GET /api/chat/quick-recommend` does *not* catch `ProviderUnavailableError`, so it 500s when the provider is down.
- **Tool-loop runaway:** after 5 rounds without a prose answer, the route returns a 200 with a "try a narrower question" message and `stop_reason: "loop_limit"`.
- **Prompt injection guard:** client-supplied `system`-role history entries are dropped before reaching the provider.
- **Hallucinated ids:** `[ANIME_ID:N]` markers from the model are stripped and never trusted; cards are resolved by title lookup instead. Titles that resolve to nothing simply produce no card (the bold text remains in the prose).
- **Fuzzy resolution risk:** title lookup falls back to `ilike '%title%'` substring matching ranked by `api_score`, so an off-canon title can resolve to the wrong (more popular) entry.
- **NSFW:** chat cards are SFW unconditionally — Hentai (hard-blocked) and Ecchi (soft-blocked) are filtered from card refs even for users with the NSFW list toggle on; the grounding candidate query is built with `include_nsfw=False`.
- **Grounding drift:** in authenticated recommend mode, any resolved card not in the scored candidate set is dropped post-hoc (small local models ignore the "pick only from candidates" rule).
- **Anonymous users:** chat works without a JWT, but the user-library tools return `{"error": "User not logged in"}` and no grounding context is attached.
- **Pills:** capped at 5, each ≤ 40 chars; the heuristic fallback only triggers on replies ending in `?` containing "or", and bails unless it extracts 2–5 clean choices. Pills render only on the latest assistant turn and disable while a request is in flight.
- **Cards:** the UI renders at most 6 per turn (`slice(0, 6)`); the system prompt caps the model at 3 per reply.
- **No persistence / no streaming:** conversations are not stored server-side, and replies arrive as a single blocking JSON response; history grows unbounded within a session since no trimming is applied.
- **Mode switch wipes the thread** by design, including any cards/pills from the previous mode.
- **Ollama specifics:** 502/503/504 from the gateway and connection/timeout errors all surface as the friendly offline state; non-native-tool models get one prompt-based fallback attempt per call, which supports only a single tool invocation per turn.

---

## Dub Reports & Admin

Bingery's dub air-date data comes from a three-tier pipeline: Tier 1 is Crunchyroll's public RSS feed, Tier 2 is the AnimeSchedule.net dub timetable, and Tier 3 is community reports — any signed-in user can report a dub air date for a specific episode, and an admin accepts or rejects it from a moderation queue. An accepted report overwrites the episode's `air_date_dub` with the highest precedence ("a human says it's right") and stamps the source as `user:<submitter_username>`.

"Admin" covers two distinct authorization schemes. The dub-report queue uses **first-user-as-admin**: the user with `id == 1` is the admin (`ADMIN_USER_ID = 1`, hardcoded in both `routes/dub_reports.py` and the frontend). Operational endpoints — the daily dub-source sync and the AniList catalog sync — instead use a shared-secret header (`X-Admin-Secret` matched against the `ADMIN_SYNC_SECRET` env var) so a GitHub Actions cron can call them without a user session.

### User flow

**Submitting a report (any signed-in user):**
1. On an anime detail page (`/anime/:id`), a signed-in user sees a ghost "Report missing dub date" button under the next-episode widget (hidden entirely when logged out).
2. Clicking it opens a modal form: an episode `<select>` (populated lazily from `GET /api/anime/<id>/episodes` only once the modal opens), a `datetime-local` input labeled as UTC, and an optional note (max 500 chars, e.g. a link to a tweet or trailer).
3. On submit the local datetime string gets `:00Z` appended (treated as UTC) and POSTed. Success shows "Thanks — your report is in the queue." and clears the fields; failure shows the server's error message inline.
4. The submission also surfaces in the submitter's own activity feed as a `dub_report` event (rendered by `frontend/src/features/activity/ActivityEntry.tsx`), including its current moderation status.

**Reviewing (admin, user id 1):**
1. Admin navigates to `/admin/dub-reports` directly — there is no nav link to this route.
2. The page defaults to the **pending** tab (tabs: pending / accepted / rejected). Each row shows episode id, submitter id, submission time, the reported dub air date, the note, and status.
3. Pending rows have Accept / Reject buttons. Accept writes the report's date to the episode (`air_date_dub`) and sets `dub_source = "user:<username>"`; Reject records the decision without touching the episode. Either way `reviewed_at`/`reviewed_by` are stamped and the queue refetches.

**Operational sync (no UI):** a GitHub Actions cron POSTs to `/api/admin/sync-dub-sources` daily; there is no frontend for this.

### Frontend

- `frontend/src/features/details/DubReportButton.tsx` — button + modal form, rendered by `frontend/src/features/details/AnimeDetailPage.tsx` (only when `useAuth` has a user). Uses `useAnimeEpisodes(animeId, open)` from `frontend/src/hooks/useSchedule.ts` so the episode list is fetched only while the modal is open; episodes are sorted client-side by `episode_number`. `toIsoZ()` converts the timezone-less `datetime-local` value into `YYYY-MM-DDTHH:MM:00Z`.
- `frontend/src/features/admin/DubReportsQueue.tsx` — the moderation page. Renders "Sign in required" when logged out and "Admins only" when `user.id !== 1`; the list query is `enabled` only for user id 1. Lazy-loaded in `frontend/src/routes.tsx` at path `admin/dub-reports`.
- `frontend/src/hooks/useDubReports.ts` — `useDubReports(status, enabled)` (React Query key `["dub-reports", status ?? "all"]`), `useCreateDubReport()` (no cache invalidation), `useUpdateDubReport()` (invalidates all `["dub-reports"]` queries on success).
- `frontend/src/lib/api.ts` — `createDubReport`, `listDubReports`, `updateDubReport` against `/dub-reports` under the `/api` base.
- Types in `frontend/src/types/models.ts` (`DubReport`, `DubReportStatus`) and `frontend/src/types/api.ts` (`CreateDubReportRequest`, `UpdateDubReportRequest`, list/single response shapes).
- Component tests: `frontend/tests/features/DubReportButton.test.tsx`, `frontend/tests/features/DubReportsQueue.test.tsx`.

### Backend

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/dub-reports` | JWT (any user) | Submit a dub air-date report for an episode |
| GET | `/api/dub-reports?status=<s>` | JWT + user id 1 | List reports for the moderation queue (newest first) |
| PATCH | `/api/dub-reports/<id>` | JWT + user id 1 | Accept or reject a report; accept writes through to the episode |
| POST | `/api/admin/sync-dub-sources` | `X-Admin-Secret` header | Run Crunchyroll RSS + AnimeSchedule syncs + synthetic seed reproject in-process |
| POST | `/api/anilist/sync` | `X-Admin-Secret` header | AniList catalog sync (same secret scheme; documented in the AniList section) |

Blueprints: `dub_reports_bp` registered at `/api/dub-reports` and `admin_bp` at `/api/admin` in `app.py`.

**Report endpoints** (`routes/dub_reports.py`): `_is_admin()` is simply `user.id == ADMIN_USER_ID` (1). POST validates `episode_id` is an integer referencing an existing `Episode`, parses `air_date` as ISO-8601 (trailing `Z` accepted; naive datetimes assumed UTC), caps `note` at 500 chars, and rejects duplicates per (submitter, episode) with 409 — the existing report is embedded in the error body. PATCH accepts only `{"status": "accepted" | "rejected"}`; on accept it overwrites `Episode.air_date_dub` **unconditionally** (Tier 3 outranks every machine source) and sets `dub_source` to `user:<username>` (falls back to `user:id<n>` if the submitter row vanished).

**Sync endpoint** (`routes/admin.py`): runs three jobs sequentially inside the live gunicorn worker (deliberately in-process — forking a fresh interpreter was OOM-killed on Fly's 256MB machine). Each job is wrapped in its own `try/except`, so one failing source doesn't abort the others; the response maps each source to its summary or `{"error": ...}`:
1. **Crunchyroll RSS** (`utils/dub_sources/crunchyroll.py`, Tier 1) — fetches the feed, extracts show title + episode number via regex, fuzzy-matches titles against the local catalog with rapidfuzz `token_set_ratio` (threshold 80.0, season/part suffixes stripped, both `title` and `title_english` considered), then upserts `Episode` rows keyed on `(anime_id, episode_number)` with `dub_source = "crunchyroll_rss"`. Writes unconditionally for matched entries.
2. **AnimeSchedule.net** (`utils/dub_sources/animeschedule.py`, Tier 2) — fetches the dub timetable JSON (Bearer token from `ANIMESCHEDULE_API_KEY`; the live API 401s without one), parses field names defensively, same fuzzy matcher (Japanese title first, English fallback), but fills `air_date_dub` **only where currently NULL**.
3. **Synthetic seed reproject** (`seed_dub_schedule.py`, invoked as `main(["--overwrite", "--top", "1500"])`) — projects sub air dates forward 56 days for top-rated airing/recently-airing anime, tagging rows `dub_source = "synthetic_lag_8w"`. Even with `--overwrite` it never touches rows whose source is `crunchyroll_rss`, `animeschedule`, or `user:%`.
4. Returns a telemetry snapshot: total dub episodes, counts grouped by `dub_source`, and counts airing in the next 7/14 days.

AniList catalog sync is deliberately excluded from this endpoint (it takes 5-15 minutes).

**Scheduled job**: `.github/workflows/refresh-schedule.yml` runs daily at 06:00 UTC (plus `workflow_dispatch`), first wakes the Fly machine by polling `/api/health` (5 retries), then curls the sync endpoint with a 600 s cap (typical run 60-90 s).

**Activity feed integration**: `routes/activity.py` joins `DubReport → Episode → Anime` for the requesting user and emits `dub_report` events (kind priority 7) with `episode_number`, `air_date`, `status`, and `note` in `meta` — reports are visible only to their submitter, and the event reflects the current moderation status.

Backend tests: `tests/test_dub_reports.py` (endpoints), `tests/test_dub_crunchyroll.py`, `tests/test_dub_animeschedule.py` (ingesters), `tests/test_admin.py` (secret auth), `tests/test_models.py` (model defaults, cascades), `tests/test_activity.py` (feed events).

### Data model

**`dub_report` table** (`models.py`, class `DubReport`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `episode_id` | Integer FK → `episode.id` | indexed, not null |
| `submitted_by` | Integer FK → `user.id` | not null |
| `air_date` | DateTime | not null; the reported dub air date |
| `status` | String(20) | default `"pending"`; `pending` / `accepted` / `rejected` |
| `note` | String(500) | nullable |
| `created_at` | DateTime | default now (UTC) |
| `reviewed_at` | DateTime | nullable; set on accept/reject |
| `reviewed_by` | Integer FK → `user.id` | nullable; the admin who reviewed |

Reports cascade-delete with their episode (`Episode.dub_reports` backref, `all, delete-orphan`), which in turn cascades from the anime.

**Owned columns on `episode`**: `air_date_dub` (DateTime, nullable, indexed) and `dub_source` (String(40), nullable) — values seen in practice: `crunchyroll_rss`, `animeschedule`, `synthetic_lag_8w`, `user:<username>`.

Client state: React Query caches `["dub-reports", <status|"all">]` and `["anime-episodes", animeId]`; admin identity comes from the `useAuth` Zustand store.

### Configuration

| Name | Kind | Default | Purpose |
|---|---|---|---|
| `ADMIN_SYNC_SECRET` | env | unset (endpoint returns 503) | Shared secret for `X-Admin-Secret` on sync endpoints; must match the GitHub Actions secret |
| `ANIMESCHEDULE_API_KEY` | env | unset (live fetch 401s) | Bearer token for the AnimeSchedule.net v3 API |
| `ADMIN_USER_ID` | constant | `1` | First-user-as-admin; duplicated in `routes/dub_reports.py` and `DubReportsQueue.tsx` |
| `MATCH_THRESHOLD` | constant | `80.0` | Minimum token-set-ratio % to accept a fuzzy title match (both ingesters) |
| `FETCH_TIMEOUT` | constant | `30` s | HTTP timeout for both external feeds |
| `CR_RSS_URL` | constant | `https://feeds.feedburner.com/crunchyroll/rss` | Tier 1 feed |
| `ANIMESCHEDULE_URL` | constant | `https://animeschedule.net/api/v3/timetables/dub` | Tier 2 feed |
| `LAG_DAYS` / `SYNTHETIC_TAG` | constants | `56` / `synthetic_lag_8w` | Synthetic seed: sub→dub projection lag and its `dub_source` tag |
| Note length cap | constant | `500` chars | Enforced server-side (400) and via `maxLength` client-side |

### Edge cases & limits

- **Status codes, POST**: 401 missing/invalid JWT or deleted user; 400 non-integer `episode_id`, unknown episode, unparseable `air_date`, non-string or >500-char note; 409 duplicate (one report per user per episode — **including rejected ones**, so a user whose report was rejected cannot resubmit for that episode); 201 on success.
- **Status codes, GET/PATCH**: 403 for any non-id-1 user; 404 unknown report id; 400 status other than `accepted`/`rejected`; 409 if the linked episode vanished between submission and accept (normally prevented by cascade, guarded anyway).
- **Re-review is allowed**: PATCH doesn't require the report to be pending, so an admin can flip an accepted report to rejected (or re-accept). Flipping to rejected does **not** roll back the episode write that the earlier accept performed.
- **Tier precedence is asymmetric in practice**: the Crunchyroll ingester writes matched entries unconditionally, without checking the existing `dub_source` — so a later daily sync **can overwrite a `user:<name>` date** if that episode shows up in the RSS feed. Only AnimeSchedule (NULL-only fill) and the synthetic seed (explicit `user:%` preserve clause) respect user data. The "Tier 3 wins" rule holds at review time, not permanently.
- **Admin model is hardcoded**: user id 1 in two places (backend + frontend). The frontend check is cosmetic; the backend 403 is the real gate. There is no `is_admin` flag — the module docstring describes that as a future replacement, and it does not exist today.
- **No pagination or filter validation** on the queue: `?status=` is matched verbatim (an unknown value returns an empty list); omitting it returns every report ever, newest first.
- **No rate limiting** on report submission beyond the per-episode dedupe; a user may file one report per episode across the whole catalog.
- **Timezone handling**: the `datetime-local` value is treated as UTC (the label says so), not the user's local timezone — a user entering a local time will be off by their UTC offset. Naive ISO strings sent to the API are likewise assumed UTC.
- **Sync resilience**: each of the three sync jobs fails independently; the endpoint still returns 200 with per-source `error` entries, and the snapshot block is itself exception-guarded. Auth failures are 401 (constant-time compare via `hmac.compare_digest`) and 503 when `ADMIN_SYNC_SECRET` isn't configured.
- **Fuzzy-match misses are observable**: both ingest summaries return `unmatched_titles` with scores, plus counters (`parsed` / `matched` / `written` / `skipped_already_filled` / `skipped_no_episode_number`), so the daily workflow log shows what failed to match.
- **Queue UX gap**: rows display raw `Episode #<id>` and `user #<id>` — the queue does not resolve anime titles or usernames, so the admin reviews against internal ids.

---

## Mobile Experience & Design System

Bingery's UI is built on a "dark cozy liquid glass" design system (introduced in the 2026-04-17 revamp, `docs/superpowers/specs/2026-04-17-bingery-revamp-design.md`): a near-black violet background, glassy translucent surfaces, an amber/peach accent family, serif display type, and a shared framer-motion vocabulary. All of it is driven by a single token module (`frontend/src/design/tokens.ts`) that feeds both Tailwind's theme and runtime code.

On top of that sits a full mobile optimization pass (2026-06-01, `docs/superpowers/specs/2026-06-01-mobile-optimization-design.md`): below 768px the app gets purpose-built native-feeling chrome — a bottom tab bar, a slim mobile header, a "More" bottom sheet, and modals that dock to the bottom as sheets — under one hard constraint: **at ≥768px the app renders byte-identically to the pre-mobile build**. This is purely a frontend feature; there are no backend changes.

### User flow

**Mobile (<768px):**
1. Every route renders inside `AppShell`, which shows the `MobileHeader` (sticky, 56px tall: Bingery wordmark + amber dot on the left, a 44px search icon button on the right that navigates to `/discover`).
2. The `BottomTabBar` is fixed to the bottom of the viewport with five thumb-sized items: **Discover · Schedule · Watchlist · For you · More**. The active tab is amber with a glowing 2px top-indicator bar.
3. Tapping **More** slides up the `MoreSheet` (spring animation): a 3-column grid of secondary destinations (Seasonal, Collections, Stats, Activity, Compare, Chat), then an account block (display name + Sign out when signed in; Sign in → `/auth` when signed out) and a 44px NSFW visibility toggle row. The sheet closes via backdrop tap, Escape, navigating, or dragging it down past ~96px.
4. Any modal in the app (collection forms, anime picker, dub-report dialog) opens as a bottom sheet: full width, rounded top corners, grab handle, slide-up entry, max 85vh.
5. Page content is padded `pb-24` so it never hides behind the fixed tab bar.

**Desktop (≥768px):** the mobile chrome is `md:hidden`; the original `Header` (wordmark + full 10-link `NavBar` + NSFW toggle + auth controls) renders instead, modals are centered scale-in dialogs, and all layout/spacing/type values are the pre-mobile ones.

### Frontend

#### App shell & routing
- `frontend/src/layout/AppShell.tsx` — root layout for every route (including `/` landing and `/auth`, per `frontend/src/routes.tsx`). Mounts the atmosphere layers (`AmbientBlobs`, `GrainOverlay`), both headers, `<main className="max-w-7xl mx-auto px-4 py-5 pb-24 md:px-6 md:py-10 md:pb-10">` wrapping `PageTransition`, then `BottomTabBar` and `MoreSheet`. Owns the single piece of chrome state: `moreOpen` (local `useState`).
- `frontend/src/layout/PageTransition.tsx` — `AnimatePresence mode="wait"` keyed on `location.pathname`; fade/slide (opacity, y: 8 → 0 in, 0 → −8 out) on every route change.
- `frontend/src/layout/RouteSkeleton.tsx` — Suspense fallback for all lazy-loaded route chunks (heading bar + 12 shimmering 2:3 poster skeletons).

#### Mobile chrome (`<768px`, all `md:hidden`)
- `frontend/src/layout/BottomTabBar.tsx` — `<nav>` with `fixed inset-x-0 bottom-0 z-40 bg-bg/80 backdrop-blur-xl border-t border-border` and `style={{ paddingBottom: "env(safe-area-inset-bottom)" }}`. Four `NavLink`s (`/discover`, `/schedule`, `/watchlist`, `/for-you`) plus the More button, each `flex-1 min-h-[56px]` with a 22px lucide icon and a `text-[10px] font-mono` label. Active state: `text-amber` plus an absolutely-positioned `h-[2px] w-8` amber bar with a glow shadow; the More button shows the same treatment while the sheet is open.
- `frontend/src/layout/MoreSheet.tsx` — framer-motion bottom sheet at `z-50`. Backdrop `bg-black/60 backdrop-blur-sm` (click to close); panel `rounded-t-2xl bg-bg-elevated max-h-[85vh] overflow-y-auto glass-edge` with a `w-9 h-1` grab handle, entering with `transitions.spring` (`y: "100%" → 0`). Drag-to-dismiss: `drag="y"`, elastic only downward (`dragElastic: { top: 0, bottom: 0.5 }`), closes when `info.offset.y > 96`. While open it listens for Escape, locks `document.body.style.overflow`, and focuses the panel (`role="dialog" aria-modal="true"`). Reads `useAuth` (`user`, `signOut`) and `useNsfw` (`visible`) and renders `NsfwToggle size="lg"`.
- `frontend/src/layout/MobileHeader.tsx` — `sticky top-0 z-30 h-14 bg-bg/70 backdrop-blur-xl backdrop-saturate-150 border-b border-border`; wordmark `Link` to `/` and a `w-11 h-11` search button → `/discover`. No nav links, no auth/NSFW controls (those live in the tab bar / More sheet).
- `frontend/src/layout/Header.tsx` — desktop header, changed only by adding `hidden md:block`; inner markup untouched. `frontend/src/layout/NavBar.tsx` holds the 10 desktop destination links (`overflow-x-auto`). `frontend/src/layout/NsfwToggle.tsx` was extracted from `Header` so both surfaces share it: `size="sm"` = 36px (desktop, byte-identical to the original), `size="lg"` = 44px (mobile touch target). It toggles `useNsfw` with `aria-pressed` and eye/eye-off SVGs.

#### Breakpoint plumbing
- `frontend/src/lib/useIsDesktop.ts` — `window.matchMedia("(min-width: 768px)")` with a change listener; exists for cases responsive classes can't express, i.e. branching framer-motion variants. Currently its only consumer is `Modal`.
- **The re-pin rule** (the desktop-preservation mechanic, spec §6): unprefixed Tailwind utilities are the *mobile* value; the previous value is re-pinned at `md:`. Invariants: never edit/delete an existing `md:`/`lg:` utility, never touch desktop-only markup, hide new mobile components with `md:hidden` and the chrome they replace with `hidden md:block`/`md:flex`. Live examples beyond the shell padding: `frontend/src/features/schedule/DayStrip.tsx` (verbatim desktop row kept under `hidden md:flex`, a new two-row mobile branch under `md:hidden`; chips `text-[18px] md:text-[24px]`; chevrons `h-11 w-11` mobile vs `h-9 w-9` desktop; sticky offset `top-14 md:top-0` to clear the h-14 MobileHeader), `frontend/src/features/schedule/EpisodeRow.tsx` (`grid-cols-[52px_1fr_auto] md:grid-cols-[60px_1fr_auto]`, `gap-3 md:gap-[18px]`, title `text-[17px] md:text-[21px]`), and `frontend/src/features/chat/ChatPage.tsx` (scroller `h-[60vh] md:h-[68vh]` so the chat card clears the tab bar).

#### Design system primitives (`frontend/src/design/`)
- `tokens.ts` — single source of truth: `palette` (core colors plus the 2026-05-24 schedule-revamp additions: peach/sage/gold/ink/mute/line/row tokens), `radius` (sm 6px · md 10px · lg 16px · xl 22px · pill 9999px), `space`, `font` stacks, `motion` (easings, durations, springs), `blur`. Compiled siblings `tokens.js`/`tokens.d.ts` exist so `frontend/tailwind.config.ts` can import the same values into Tailwind's theme — every palette entry becomes a semantic class (`bg-bg`, `bg-bg-elevated`, `bg-surface`, `text-text-muted`, `border-border-strong`, `text-amber`, `text-peach`, `bg-row-bg`, …). Components use these classes, never raw hex.
- `Modal.tsx` — the responsive modal/bottom-sheet. ≥768px: centered dialog, `scale 0.96→1` + `y 8→0`, `md:rounded-xl md:max-h-[92vh]`, `maxWidth` prop (default `"640px"`). <768px: docks to the bottom (`items-end`), `rounded-t-2xl max-h-[85vh]`, mobile-only grab handle, slide-up `y:"100%"→0` with `transitions.spring`, `env(safe-area-inset-bottom)` padding. The variant branch uses `useIsDesktop`; the desktop values are deliberately identical to the pre-mobile component. All consumers (`features/collections/CollectionsListPage.tsx`, `features/collections/CollectionDetailPage.tsx`, `features/details/DubReportButton.tsx`) were upgraded with zero per-consumer changes.
- `Button.tsx` — pill-shaped `motion.button`; variants `primary` (glass-peach gradient, amber border, inset highlight), `ghost`, `glass`, `danger`; sizes `sm` h-8 / `md` h-10 / `lg` h-12; built-in hover scale 1.02 / tap scale 0.97 (`transitions.springSnappy`), `loading` spinner, `leading`/`trailing` slots. Intentionally **not** resized for mobile (spec decision: touch-target fixes are surgical, not global).
- `Input.tsx` — labeled input, h-10, `rounded-lg`, surface fill, amber `focus-within` ring, inline error text (danger border/ring when set).
- `GlassCard.tsx` — `rounded-xl border border-border glass-edge backdrop-blur-md` with `tone` = `default | warm` (amber gradient) `| cool` (violet gradient) and an `elevated` shadow flag.
- `Badge.tsx` (hex `color` prop, alpha-suffixed bg/border), `Skeleton.tsx` (shimmer sweep via an inline `@keyframes`), `StarRating.tsx`, `ScrollReveal.tsx` (IntersectionObserver fade-up, `triggerOnce`).
- `motion.ts` — re-exports tokens as framer-motion `transitions` (`ease`, `easeFast`, `easeSlow`, `spring` = soft 260/28, `springSnappy` = 420/32) and variants (`fadeInUp`, `fadeIn`, `scaleIn`, `pressDown`, `staggerChildren`). New components are expected to import these rather than invent durations.
- `AmbientBlobs.tsx` + `GrainOverlay.tsx` — the fixed, pointer-events-none atmosphere behind every page: two huge (720px/640px) radial amber/violet blobs at `blur-[160px]` drifting on 18s/22s infinite loops, plus an SVG grain texture (`/grain.svg` via the `bg-grain` Tailwind utility) at 0.14 opacity with `mix-blend-overlay`.

#### The GL surface
`frontend/src/design/LiquidGLSurface.tsx` wraps content in a real WebGL refraction surface using the vendored `naughtyduk/liquidGL` script (`frontend/public/vendor/liquidgl.js`):
- The script is lazy-loaded on first mount via a module-level `scriptPromise` singleton (one `<script src="/vendor/liquidgl.js">` injection per session), then `window.LiquidGL.init({ container, refraction, dispersion, blur, tint })` is called; the instance is destroyed on unmount.
- If the user has `prefers-reduced-motion: reduce`, the effect is skipped entirely; if the script fails to load, the error is swallowed and the static fallback styling (`bg-surface-strong backdrop-blur-xl border border-border glass-edge`) — which always renders underneath — remains.
- Sole consumer today: the anime detail hero (`frontend/src/features/details/DetailHero.tsx`).

#### Fonts & global CSS
- `frontend/index.html` loads **Geist**, **Geist Mono**, and **Instrument Serif** from Google Fonts and sets `<meta name="theme-color" content="#080510">`.
- `frontend/src/index.css` additionally imports `@fontsource` **Fraunces** 400/600, **Inter** 400/500/600, and **JetBrains Mono** 400 — but the `font` stacks in `tokens.ts` are `Instrument Serif…`, `Geist…`, `Geist Mono…`, so the Google-Fonts faces win and the @fontsource bundles are loaded-but-unreferenced (a pre-existing mismatch the mobile spec explicitly declared out of scope).
- Global base styles: `color-scheme: dark`, 15px/1.55 body, `h1–h3` in `font-display` at weight 600 with `-0.01em` tracking, `overflow-x: hidden` on body (guards against page-level horizontal scroll from chip rows), amber `::selection`, and two custom utilities — `.glass-edge` (inset top highlight + inset bottom shade + deep drop shadow, the signature glass look) and `.ring-amber`.

### Backend

None. This feature is entirely client-side — no endpoints, no server-side logic. (The mobile spec's hard scope rule: "No backend changes.")

### Data model

No server-side tables. Client state it owns or depends on:
- `moreOpen: boolean` — local `useState` in `AppShell`, threaded to `BottomTabBar` (active styling) and `MoreSheet` (visibility).
- `useIsDesktop` — derived `matchMedia` state for the 768px boundary.
- Consumed zustand stores: `useAuth` from `frontend/src/stores/auth.ts` (`user`, `signOut` for the MoreSheet/Header account blocks) and `useNsfw` from `frontend/src/stores/nsfw.ts` (`visible`, `toggle` for the NSFW toggle).
- Design tokens are static `as const` objects in `frontend/src/design/tokens.ts`; no persistence.

### Configuration

No env vars — everything is constants in code:
- **Breakpoint:** 768px (Tailwind default `md`; hardcoded as `"(min-width: 768px)"` in `frontend/src/lib/useIsDesktop.ts`). The spec forbids custom Tailwind breakpoints.
- **LiquidGLSurface defaults:** `refraction = 0.04`, `dispersion = 0.015`, `blur = 6`, `tint = "rgba(255,255,255,0.02)"`; script path `/vendor/liquidgl.js`.
- **Modal:** `maxWidth = "640px"` default; mobile sheet `max-h-[85vh]`, desktop `max-h-[92vh]`.
- **MoreSheet:** drag-dismiss threshold 96px; `max-h-[85vh]`.
- **Tab bar:** items `min-h-[56px]`; main content reserves `pb-24` (6rem) for it.
- **Z-layering:** headers/DayStrip `z-30` → BottomTabBar `z-40` → MoreSheet/Modal `z-50`; atmosphere layers `z-0` under a `z-10` content wrapper.
- **Motion constants:** durations 0.18/0.28/0.45/0.7s; springs soft (260, 28) and snappy (420, 32); easings `[0.22,1,0.36,1]` and `[0.16,1,0.3,1]` (all in `tokens.ts`).

### Edge cases & limits

- **Desktop preservation is structural, not tested-in:** because no rule that applies at ≥768px was modified (re-pin rule invariants), the ≥768px render is unchanged by construction. When editing any component, put mobile values in the unprefixed base and re-pin the existing value at `md:` — never edit an existing `md:`/`lg:` utility.
- **Safe-area padding is currently inert in normal browsers:** `frontend/index.html`'s viewport meta lacks `viewport-fit=cover`, so `env(safe-area-inset-bottom)` resolves to 0 in standard browser contexts; the padding on `BottomTabBar`, `MoreSheet`, and the mobile `Modal` only takes effect where the viewport extends into the home-indicator inset.
- **LiquidGL failure modes:** a failed script load is cached forever (the module-level rejected promise is reused), so the effect silently stays off for the session and the static glass fallback shows; `prefers-reduced-motion` disables it entirely. `AmbientBlobs`, by contrast, has **no** reduced-motion guard — its drift loops run unconditionally.
- **Scroll-lock asymmetry:** `MoreSheet` locks body scroll while open; the shared `Modal` does not (it only handles Escape + backdrop click). Background pages remain scrollable behind modals.
- **Focus return:** `MoreSheet` moves focus into the panel on open but does not restore focus to the More button on close (the spec asked for restoration; the code doesn't implement it).
- **Landing and `/auth` get mobile chrome too:** both are children of `AppShell`, so the tab bar and mobile header render on them as well.
- **Touch targets are surgical:** 44px hit areas were applied only where elements were undersized (NsfwToggle `size="lg"`, DayStrip chevrons `big`, MobileHeader search). The shared `Button` keeps `sm` = 32px even on mobile, by design.
- **`Badge` requires 6-digit hex colors:** it builds backgrounds/borders by string-appending alpha suffixes (`color + "18"`); passing `rgba(...)` produces invalid CSS.
- **Route transitions block on exit:** `PageTransition` uses `AnimatePresence mode="wait"`, so new route content appears only after the previous page's exit animation completes (~0.28s).
- **Token duplication hazard:** `tokens.ts` and the compiled `tokens.js` must stay in sync — Tailwind config consumes the compiled copy, runtime code the TypeScript one.
- **Known accepted patterns:** horizontal-scroll chip rows (Discover FilterBar, Watchlist StatusTabs, Stats heatmap) are intentional on mobile; body-level `overflow-x: hidden` prevents them from causing page scroll. Tablet landscape (768–1023px) intentionally gets the desktop layout — there is no tablet-specific design.

---

## Architecture, Data Sync & Deployment

Bingery is a single Flask application (`app.py`) that exposes a JSON API under `/api/*` and serves the Vite-built React SPA from the same process. All persistent state lives in one SQLAlchemy database — SQLite by default, with URL-level Postgres support — and the anime catalog itself is not user-generated: it is ingested from the AniList GraphQL API by a resumable CLI sync pipeline (`sync_anilist.py` + `utils/anilist.py`) and refreshed on a schedule. The production target is a single Fly.io machine (region `yyz`) built from the multi-stage `Dockerfile`, with the SQLite file on a persistent volume at `/data`.

This section covers the app factory and blueprint map, the AniList ingestion/sync pipeline, the database backends, the production boot guards, and the deployment/scheduling story (Fly.io primary; a Heroku-style `Procfile` is also present; the Render config was retired 2026-07-10).

### User flow

This is an operator/developer-facing feature; the "user" is whoever runs and deploys the app.

1. **Local dev.** Copy `.env.example` → `.env`, `pip install -r requirements.txt`, `python seed.py` (bootstraps genres + ~20 curated titles + demo data), then `python app.py` (Flask debug server on `FLASK_PORT`, default 5000). The frontend runs separately via Vite on port 5173, proxying `/api` to `127.0.0.1:5000` (`frontend/vite.config.ts`). `app.py` loads `.env` via `python-dotenv` *before* importing config/blueprints, because several modules resolve env at import time.
2. **Catalog ingestion.** Run `python sync_anilist.py` (default `--resume`) to walk the full AniList catalog year-by-year (1960 → current year + 1), upserting `Anime` and `Episode` rows. `--full` restarts from 1960; `--dry-run`, `--max-pages N`, `--since YYYY-MM-DD` are available. `--format FMT` / `--all-orphan-formats` runs the orphan-catcher pass for titles AniList stores with `seasonYear: null`. Full catalog ≈ 25k anime, ~10–30 min wall clock. A smaller ad-hoc sync also exists: `python -m utils.anilist --mode popular|top|trending|seasonal|search`.
3. **Deploy to Fly.** `fly launch --no-deploy`, `fly volumes create bingery_data --size 1`, `fly secrets set JWT_SECRET_KEY=… SECRET_KEY=… CORS_ORIGINS=… …`, `fly deploy`, then ship the SQLite file once via `fly ssh sftp` → `/data/bingery.db` (setup steps are documented in comments at the top of `fly.toml`; the broader plan including the Cloudflare Tunnel for home-PC Ollama is in `docs/DEPLOYMENT.md`, with helper scripts `tunnel.ps1` / `tunnel-up.cmd` / `tunnel-stop.cmd` at repo root).
4. **Steady state.** A GitHub Actions workflow (`.github/workflows/refresh-schedule.yml`) runs daily at 06:00 UTC: it polls `GET /api/health` to wake the auto-stopped Fly machine, then POSTs `/api/admin/sync-dub-sources` with the `X-Admin-Secret` header to refresh dub data in-process. The AniList *catalog* sync is deliberately not on this schedule — it is run manually when catalog status fields look stale.

### Frontend

The frontend's involvement in this feature is build/serving plumbing, not UI:

- `frontend/src/lib/api.ts` — resolves the API base URL. If `VITE_API_URL` is set at build time (documented in `frontend/.env.example`), it is normalized (trailing slashes stripped, `/api` appended unless already present) — this is the split-host mode (e.g. Cloudflare Pages frontend + Fly backend). If unset: `http://localhost:5000/api` when the page is on `localhost`/`127.0.0.1`, otherwise same-origin `${window.location.origin}/api` (matches the Docker setup where Flask serves the SPA).
- `frontend/vite.config.ts` — dev server on port 5173 with a `/api` proxy to `http://127.0.0.1:5000`; production build outputs to `frontend/dist` with sourcemaps.
- Serving: `_static_root()` in `app.py` picks `frontend/dist/` as Flask's static folder when it exists and contains `index.html`, otherwise falls back to the legacy `static/` bundle. The catch-all route serves real files when they exist and `index.html` for everything else, so SPA deep links work.

### Backend

#### App factory and blueprint map

`create_app(config_class=Config)` in `app.py` initializes SQLAlchemy (`models.db`), CORS (scoped to `r"/api/*"`, origins from `CORS_ORIGINS`, `supports_credentials=False`), `JWTManager`, and Bcrypt (shared instance imported from `routes/auth.py`), registers 16 blueprints, defines the health check / SPA / error handlers, and calls `db.create_all()` inside an app context on every boot. A module-level `app = create_app()` exists for gunicorn (`gunicorn app:app`).

| Blueprint | Module | URL prefix |
|---|---|---|
| `auth_bp` | `routes/auth.py` | `/api/auth` |
| `anime_bp` | `routes/anime.py` | `/api/anime` |
| `ratings_bp` | `routes/ratings.py` | `/api` |
| `anilist_bp` | `routes/anilist.py` | `/api/anilist` |
| `chatbot_bp` | `routes/chatbot.py` | `/api/chat` |
| `recommend_bp` | `routes/recommend.py` | `/api/recommend` |
| `watchlist_bp` | `routes/watchlist.py` | `/api/watchlist` |
| `search_bp` | `routes/search.py` | `/api/search` |
| `collections_bp` | `routes/collections.py` | `/api/collections` (set at registration) |
| `stats_bp` | `routes/stats.py` | `/api/stats` (registration) |
| `activity_bp` | `routes/activity.py` | `/api/activity` (registration) |
| `seasonal_bp` | `routes/seasonal.py` | `/api/seasonal` (registration) |
| `compare_bp` | `routes/compare.py` | `/api/compare` (registration) |
| `schedule_bp` | `routes/schedule.py` | `/api` (registration) |
| `dub_reports_bp` | `routes/dub_reports.py` | `/api/dub-reports` (registration) |
| `admin_bp` | `routes/admin.py` | `/api/admin` (registration) |

Error handlers: 404 on `/api/*` paths returns JSON `{"error": "Not found."}`; 404 anywhere else serves `index.html` (SPA fallback); 500 returns JSON.

#### Endpoints owned by this feature

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | None | Liveness probe: `{"status": "ok", "service": "bingery-api"}`. Used by the Docker `HEALTHCHECK`, Fly's `[[http_service.checks]]`, and the GH Actions wake-up loop. |
| GET | `/` and `/<path>` | None | SPA serving — real static file if it exists, else `index.html`. |
| GET | `/api/anilist/search?q=&page=&per_page=` | None | Live AniList title search (results NOT persisted). `per_page` capped at 25. 400 if `q` missing; 502 on AniList failure. |
| GET | `/api/anilist/anime/<anilist_id>` | None | Live AniList details for one title. 502 on failure. |
| GET | `/api/anilist/trending?per_page=` | None | Trending straight from AniList (`per_page` clamped 1–50). |
| GET | `/api/anilist/seasonal?year=&season=&per_page=` | None | Season listing from AniList; 400 unless `year` is int and `season` ∈ WINTER/SPRING/SUMMER/FALL. |
| POST | `/api/anilist/sync` | `X-Admin-Secret` header | On-demand DB sync. Body `{mode, pages, query?, season?, year?}`; modes `popular|top|trending|seasonal|search`; `pages` clamped 1–10. 503 if `ADMIN_SYNC_SECRET` unset, 401 on mismatch, 502 on sync failure. Runs synchronously inside the request. |
| POST | `/api/admin/sync-dub-sources` | `X-Admin-Secret` header | In-process dub refresh: Crunchyroll RSS ingest + AnimeSchedule.net ingest + synthetic dub seed reproject (`seed_dub_schedule.main(["--overwrite", "--top", "1500"])`), plus a telemetry snapshot. Per-source errors are caught and reported in the JSON body rather than failing the whole run. 503/401 as above. |

Both admin-gated endpoints compare secrets with `hmac.compare_digest` (constant-time).

#### AniList client (`utils/anilist.py`)

`AniListClient` wraps `https://graphql.anilist.co` with a `requests.Session`:

- **Rate limiting** — sleeps so consecutive requests are ≥ `RATE_LIMIT_DELAY` (0.7 s) apart, targeting ~85 req/min against AniList's documented 90 req/min cap. On HTTP 429 it honors `Retry-After` (capped at 60 s) and retries up to 2 times before raising.
- **Normalization** — `_normalize_anime()` converts AniList media to Bingery's shape: score rescaled 0–100 → 0–10 (null stays `None`), status/source/season enums mapped to display strings, main-studio extraction, basic HTML stripping in synopses, tags filtered to rank ≥ 60.
- **Queries** — `SEARCH_QUERY`, `POPULAR_QUERY`, `DETAIL_QUERY` (all share the `AnimeFields` fragment), `CATALOG_QUERY` (paginated by `seasonYear`, includes `airingSchedule` + `nextAiringEpisode`), `CATALOG_QUERY_BY_FORMAT` (paginated by `MediaFormat`), and a self-contained `RELATIONS_QUERY` for the franchise strip.
- **Relations cache** — `get_anime_relations()` caches per-title results in the in-process dict `_RELATIONS_CACHE` for `RELATIONS_CACHE_TTL` (24 h), bounded at `RELATIONS_CACHE_MAX` (512) entries with expired-first then oldest-first eviction. Valid as a global cache only because production runs a single gunicorn worker.
- **Franchise traversal** — `assemble_franchise()` does a bounded BFS over relation edges (`PREQUEL/SEQUEL/PARENT/SIDE_STORY/ALTERNATIVE` only), capped at `FRANCHISE_MAX_NODES` (25 API calls) and `FRANCHISE_MAX_DEPTH` (5).

#### Catalog sync pipeline (`sync_anilist.py`)

- **Why year-chunking:** AniList caps deep page-based pagination at offset 5000 and exposes no `id_greater` on `Media`, so the full catalog is walked one `seasonYear` at a time (no year exceeds 5000 titles). Outer loop: years `1960 → current UTC year + 1`; inner loop: ordinary pagination at 50/page with 0.7 s sleeps between pages (`PAGE_SLEEP_SECONDS`).
- **Resumability:** the singleton `AniListSyncState` row's `last_page` column is *repurposed as "last completed year"*; `--resume` (the default) restarts at `last_page + 1`, and the year counter only advances after a year fully completes. `status` transitions `running → idle` (success or Ctrl-C) or `error` (with `error_message` persisted); `last_full_at` is stamped when a `--full` run finishes.
- **Upsert semantics:** `process_media_entry()` calls `sync_anime_to_db()` (`utils/anilist.py`), which matches by `anilist_id` then `mal_id`, updates only non-`None` fields (so an unrated AniList entry never wipes a real score), and rebuilds the `official_genres` links. Episode rows are upserted by `(anime_id, episode_number)` from `airingSchedule` + `nextAiringEpisode`, setting `air_date_sub` with `sub_source="anilist"`. Fully idempotent — re-running refreshes rather than duplicates.
- **Orphan catcher:** `run_format_sync()` paginates by `format` (`SPECIAL, OVA, ONA, MUSIC, TV_SHORT` via `--all-orphan-formats`) to reach `seasonYear: null` titles the year-chunker can never see, bailing at page 100 (`MAX_PAGES_PER_FORMAT`) to stay under the 5000-offset cap. It does not touch `AniListSyncState`.

#### Scheduled jobs

- **GitHub Actions** (`.github/workflows/refresh-schedule.yml`): daily 06:00 UTC + manual dispatch; wakes the Fly machine via `/api/health` (5 retries), then `curl`s `/api/admin/sync-dub-sources` with a 10-minute cap (typical run 60–90 s). Runs the syncs *inside* the live gunicorn worker because spawning a fresh `python sync_*.py` interpreter (~100 MB of Flask+SQLAlchemy imports) gets OOM-killed on Fly's 256 MB VM; in-process the peak delta is ~25 MB.
- **Retired: Render crons** (removed 2026-07-10 along with `render.yaml`): the weekly AniList resync, 6-hourly Crunchyroll RSS, and daily AnimeSchedule jobs ran against a separate Render Postgres the Fly app never read. Their replacements live in the GH Actions workflow above (daily window status refresh, Sunday seasonal pull, daily dub sync via admin endpoints).

### Data model

Owned by this feature (all in `models.py`):

- **`Anime`** — the synced catalog row: `mal_id` / `anilist_id` (both unique, nullable, indexed), `title` / `title_english` / `title_japanese`, `synopsis`, `api_score` (0–10, from AniList), `popularity`, `year`, `season`, `episodes`, `studio`, `image_url`, `banner_url`, `status`, `source`, timestamps.
- **`Genre`** + association table **`anime_genres`** — official genres synced from AniList; `Genre.category` ∈ `standard|demographic|theme|setting`.
- **`Episode`** — per-episode air dates fed by the sync: `anime_id` FK, `episode_number`, `air_date_sub` / `air_date_dub`, `sub_source` (default `"anilist"`) / `dub_source`, unique on `(anime_id, episode_number)`.
- **`AniListSyncState`** — singleton sync bookkeeping: `last_page` (= last completed year), `last_run_at`, `last_full_at`, `total_synced`, `status` (`idle|running|error`), `error_message`. Created lazily by `get_or_create_sync_state()`.

Database backends: default is SQLite at `<repo>/bingery.db` (`config.py` builds the URI from `BASE_DIR`); Docker/Fly override to `sqlite:////data/bingery.db` on the persistent volume. `config.py` rewrites Render/Heroku-style `postgres://` URLs to `postgresql://` for SQLAlchemy 2.x compatibility. Schema management is `db.create_all()` on boot — no Alembic; the only migration tooling is the one-off `migrate_watchlist.py`.

### Configuration

| Variable / constant | Default | Effect |
|---|---|---|
| `FLASK_ENV` | unset (dev) | `production`/`prod` arms the boot guards. When unset, `config._is_production()` **fails closed on Fly**: `FLY_APP_NAME` being present (always set in the Fly runtime) also counts as production. |
| `DATABASE_URL` | `sqlite:///<repo>/bingery.db` | SQLAlchemy URI; `postgres://` → `postgresql://` fixup applied. Dockerfile/fly.toml set `sqlite:////data/bingery.db`. |
| `SECRET_KEY` / `JWT_SECRET_KEY` | dev sentinel strings | Must be overridden in production (guarded). JWT access tokens expire after 7 days (`JWT_ACCESS_TOKEN_EXPIRES`). |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins for `/api/*`. `*` is rejected in production. |
| `EMAIL_PROVIDER` / `BREVO_API_KEY` / `EMAIL_FROM` | `console` / empty / empty | Owned by the auth feature, but enforced by this feature's boot guard: production requires `brevo` plus both credentials. |
| `ADMIN_SYNC_SECRET` | unset | Enables `POST /api/anilist/sync` and `POST /api/admin/sync-dub-sources`; when unset both return 503. |
| `FLASK_PORT` | `5000` | Dev server port (`python app.py` only). |
| `PORT` | `5000` (Dockerfile) | Used by the Procfile's gunicorn bind; the Docker CMD hardcodes `0.0.0.0:5000`. |
| `VITE_API_URL` | unset | Frontend build-time backend origin for split-host deployments; unset = localhost-or-same-origin heuristic. |
| `RATE_LIMIT_DELAY` / `PAGE_SLEEP_SECONDS` | 0.7 s each | AniList request pacing (client-level and sync-loop-level). |
| `RELATIONS_CACHE_TTL` / `RELATIONS_CACHE_MAX` | 24 h / 512 | Relations cache tuning. |
| `FRANCHISE_MAX_NODES` / `FRANCHISE_MAX_DEPTH` | 25 / 5 | Franchise BFS bounds. |
| `FIRST_YEAR` / `DEFAULT_END_YEAR_OFFSET` | 1960 / +1 | Catalog sync year range. |
| `MAX_PAGES_PER_FORMAT` | 100 | Orphan-catcher page cap (5000-offset guard). |
| Gunicorn (Docker CMD) | 1 worker, 4 threads, timeout 180 s | Single worker so all 256 MB is available per request and in-process caches stay coherent; long timeout for ~60 s Ollama chat calls. |

Fly runtime knobs (`fly.toml`): app `bingery`, region `yyz`, `force_https`, `auto_stop_machines = "stop"` with `min_machines_running = 0` and auto-start, request concurrency soft 50 / hard 100, `shared-cpu-1x` 256 MB VM, volume `bingery_data` mounted at `/data` (1 GB initial).

### Edge cases & limits

- **Production boot guards fail hard.** With production detected, `config.py` raises `SystemExit(2)` with a `FATAL` message listing every problem (dev `SECRET_KEY`/`JWT_SECRET_KEY`, wildcard `CORS_ORIGINS`, non-Brevo email provider, or missing Brevo credentials). The Fly fallback (`FLY_APP_NAME`) means deleting `FLASK_ENV` from `fly.toml` cannot silently disable the guards.
- **AniList rate limit handling**: 0.7 s pacing targets ~85 of the allowed 90 req/min; on 429 the client waits `Retry-After` (≤ 60 s) and retries at most twice before raising "rate limit persisted after retries".
- **5000-offset wall + `seasonYear: null` gap.** Year-chunking sidesteps AniList's deep-pagination cap; titles with no `seasonYear` (mostly old specials/OVAs) are unreachable by the main sync and need the `--format` orphan-catcher pass, itself hard-capped at page 100 per format.
- **`--since` is effectively a no-op.** The catalog query never requests `updatedAt`, and `_normalize_anime()` doesn't carry it, so the cutoff filter (which reads `media["updatedAt"]`) never matches. The CLI help honestly labels it "best-effort"; callers rely on upsert idempotency, not on `--since`, for correctness.
- **Sync concurrency is unguarded.** `AniListSyncState.status` is advisory; nothing prevents two simultaneous sync runs. Fine for the manual/cron usage pattern, but worth knowing.
- **`db.create_all()` is not a migration system** — it creates missing tables but never alters existing columns. Schema changes on a live volume require manual work (cf. `migrate_watchlist.py`).
- **Postgres support is URL-level only.** `config.py` does the `postgres://` scheme fixup, but `requirements.txt` pins no Postgres driver (`psycopg2` absent) — any future Postgres deploy needs the driver added. The shipped production path is SQLite-on-volume.
- **Single-worker assumptions.** The relations cache (and other in-process caches) are global only because gunicorn runs one worker; raising `--workers` or adding Fly machines silently splits them, and SQLite-on-volume rules out horizontal scaling anyway (acknowledged trade-off in `docs/DEPLOYMENT.md`).
- **Cold starts.** `min_machines_running = 0` means the Fly machine stops when idle; the first request takes seconds. The GH Actions job compensates with a 5-attempt `/api/health` wake loop before syncing.
- **Memory ceiling drives design.** The 256 MB VM is why admin syncs run in-process (POST endpoint) instead of `fly ssh` + a fresh interpreter, and why the daily refresh deliberately excludes the 5–15 min AniList catalog sync.
- **Synchronous admin sync requests.** `POST /api/anilist/sync` (≤ 10 pages ≈ 500 titles) and `/api/admin/sync-dub-sources` (~60–90 s) block a request thread for their whole duration; gunicorn's 180 s timeout is the de facto ceiling.
- **Graceful degradation paths**: live-AniList endpoints return 502 (with `logger.exception` server-side) when AniList is down — the local catalog keeps serving; the SPA fallback serves the legacy `static/` bundle if `frontend/dist` is missing; per-source failures in the dub sync are reported per-key in the response instead of aborting the run.
- **Health checks at three layers**: Docker `HEALTHCHECK` (curl, 30 s interval / 5 s timeout / 20 s start period / 3 retries), Fly HTTP check (same cadence, `GET /api/health`), and Render `healthCheckPath` — all hitting the same endpoint.
- **Alternative deploy configs are present but secondary**: `Procfile` (Heroku-style, 2 workers) coexists with the primary Fly setup (`render.yaml` was retired 2026-07-10); `docs/DEPLOYMENT.md` predates parts of the implementation (e.g. it lists email login as deferred, which now exists) — the code and `fly.toml` are authoritative.
