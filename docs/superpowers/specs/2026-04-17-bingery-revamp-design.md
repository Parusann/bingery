# Bingery Revamp — Design Spec

**Date:** 2026-04-17
**Status:** Approved pending review

## 1. Overview

Bingery is being rebuilt with two goals: (1) switch the AI backend from the hosted Anthropic API to a runtime-switchable provider that defaults to a local Ollama model (`gemma4:31b`) but can fall back to Anthropic for production, and (2) complete a visual redesign as a "dark cozy liquid glass" premium-craft UI. All existing features are preserved. Five new features are added: a stats dashboard, custom collections, a seasonal calendar, an activity timeline, and a side-by-side compare view.

## 2. Goals & Non-goals

**Goals**
- Preserve every feature, model, and API endpoint from the current build.
- Introduce an AI provider abstraction so Ollama and Anthropic are interchangeable via a single env var.
- Replace the single-file CDN-based React frontend with a proper Vite + React + TypeScript + Tailwind + Framer Motion build.
- Apply a coherent dark-glass visual system with real WebGL refraction on hero surfaces (via `naughtyduk/liquidGL`).
- Add five new features: Stats, Collections, Seasonal calendar, Activity timeline, Compare.
- Maintain Render deployability alongside local-Ollama workflow.

**Non-goals (this pass)**
- Social features (follows, friend comparisons, shared feeds).
- Notifications or digest email.
- Native mobile apps (responsive web is sufficient).
- Anime sources beyond AniList.
- Public API / OAuth for third parties.

## 3. Architecture

### 3.1 Backend (Python / Flask)

Kept: Flask 3, SQLAlchemy, Flask-JWT-Extended, Flask-Bcrypt, Flask-CORS, PostgreSQL/SQLite auto-switch.

Added:
- `utils/ai_provider.py` — abstract `AIProvider` with `OllamaProvider` and `AnthropicProvider` implementations, selected at runtime by `AI_PROVIDER` env var (`ollama` | `anthropic`).
- `utils/ai_tools.py` — single source of truth for tool definitions as JSON Schema; each provider translates to native format.
- New route modules: `routes/collections.py`, `routes/stats.py`, `routes/activity.py`, `routes/seasonal.py`, `routes/compare.py`.
- `routes/chatbot.py` is rewired to call `AIProvider` instead of `anthropic` directly.

### 3.2 Frontend (TypeScript / React)

New `frontend/` subtree replaces `static/index.html`.

- **Build:** Vite 5 + React 18 + TypeScript.
- **Styling:** Tailwind CSS v3 with a custom plugin exposing glass/grain/motion utilities.
- **State:** TanStack Query (server state, caching, mutations). Zustand (auth session, UI preferences, onboarding flags).
- **Routing:** React Router v6. Hash routing is dropped.
- **Motion:** Framer Motion. A shared `motion.config.ts` defines spring presets, easing curves, and stagger utilities.
- **WebGL glass:** `naughtyduk/liquidGL` mounted on ≤6 hero surfaces per route (nav, detail panel, chat drawer, modal). Other surfaces use CSS approximation for performance.
- **Fonts:** self-hosted variable fonts — Fraunces (display serif), Inter (body sans), JetBrains Mono (data).
- **Output:** `frontend/dist/` copied to `static/dist/` as part of the build; Flask serves from there.

### 3.3 Deployment modes

Controlled entirely by environment variables.

**Local dev**
```
AI_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:31b
DATABASE_URL=sqlite:///bingery.db
```

**Render (prod)**
```
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=<secret>
DATABASE_URL=<postgres url auto-set by Render>
```

`build.sh` is updated to run `cd frontend && npm ci && npm run build && cd ..` before Python dependency install and seed.

## 4. AI Provider Abstraction

### 4.1 Interface

```python
class AIProvider(Protocol):
    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> AIResponse: ...

    def stream(self, ...) -> Iterator[AIChunk]: ...
```

`AIResponse` normalizes across providers: `{text, tool_calls, stop_reason, usage}`.

### 4.2 OllamaProvider

- POSTs to `{OLLAMA_URL}/api/chat` with `model`, `messages`, optional `tools`.
- First attempts native tool calls via Ollama's `tools` field. Parses `message.tool_calls` from response.
- If the model returns a malformed or missing `tool_calls` for a request that included tools, falls back to **prompt-based JSON tool use**: inject tool schemas into the system prompt with explicit JSON output instructions, parse the first JSON object in the response body.
- Detection of tool-use capability is memoized per-process after first successful native call.

### 4.3 AnthropicProvider

- Thin wrapper around existing `anthropic` SDK code from `routes/chatbot.py`.
- Default model: `claude-sonnet-4-6`. Configurable via `ANTHROPIC_MODEL`.
- Translates the shared `ToolSchema` JSON into Anthropic's `input_schema` format (they're already compatible with minor field renames).

### 4.4 Tool definitions

The five existing tools move to `utils/ai_tools.py` as JSON Schema objects:
- `search_anime_database`
- `get_user_taste_profile`
- `get_user_watchlist`
- `get_anime_details`
- `search_anilist`

Each provider adapts this shared schema to its own format.

## 5. Data Model Changes

Two new models added. All existing models are untouched.

```python
class Collection(db.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, FK(User.id), nullable=False)
    name = Column(String(80), nullable=False)
    description = Column(String(500))
    color = Column(String(16), default="amber")  # palette keyword
    icon = Column(String(32))                    # icon keyword
    is_public = Column(Boolean, default=False)
    share_token = Column(String(32), unique=True, nullable=True)  # generated on first public toggle
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class CollectionItem(db.Model):
    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, FK(Collection.id), nullable=False)
    anime_id = Column(Integer, FK(Anime.id), nullable=False)
    note = Column(String(500))
    added_at = Column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("collection_id", "anime_id"),)
```

Activity feed and stats are derived at query time from existing tables (`Rating.created_at`, `WatchlistEntry.updated_at`, `FanGenreVote.created_at`). No new models for those features.

## 6. API Surface

### 6.1 Preserved (unchanged shapes)
All 25 existing endpoints: auth (register/login/profile), anime (list/detail/genres/top), ratings (CRUD + review), fan genres (vote/aggregate/allowed), watchlist (status/favorites/bulk/stats), search (autocomplete/advanced), recommend (for-you/similar/taste-profile/onboarding), chat (message/quick), anilist (search/detail/sync/trending/seasonal), health.

### 6.2 New endpoints

**Collections** — `/api/collections/*`
- `GET /` — list current user's collections.
- `POST /` — create.
- `GET /<id>` — detail with items.
- `PATCH /<id>` — update name/color/icon/description/public.
- `DELETE /<id>`.
- `POST /<id>/items` — add anime to collection.
- `DELETE /<id>/items/<anime_id>` — remove.
- `GET /public/<share_token>` — view-only public accessor.

**Stats** — `/api/stats/*`
- `GET /` — aggregate dashboard payload: genre radar data, year distribution, score distribution, top studios, hours-watched estimate, top fan tags.
- `GET /genres` — detail breakdown for radar drill-in.
- `GET /timeline` — year-by-year summary.

**Activity** — `/api/activity`
- `GET /?limit=50&before=<timestamp>` — paginated reverse-chron feed of current user actions, each item shaped as `{type, anime_id, anime_title, cover, timestamp, meta}`.
- `GET /on-this-day` — activity from this date in prior years.

**Seasonal** — `/api/seasonal`
- `GET /?season=WINTER&year=2026` — anime for a season overlaid with current user's statuses.
- `GET /airing-now` — convenience endpoint for currently airing.

**Compare** — `/api/compare`
- `GET /?a=<anime_id>&b=<anime_id>` — normalized payload for two anime plus user's ratings, shared genres, shared fan tags, shared studios, review text.

## 7. Visual Design System

### 7.1 Palette (CSS variables)

```
--bg-deep:      #080510
--bg-panel:     rgba(255,255,255,0.06)
--blob-warm:    rgba(230,166,128,0.45)
--blob-cool:    rgba(140,110,200,0.30)
--accent:       #e6a680   /* muted amber */
--accent-alt:   #b89ac4   /* soft violet */
--text-1:       rgba(255,255,255,0.95)
--text-2:       rgba(255,255,255,0.70)
--text-3:       rgba(255,255,255,0.42)
--line:         rgba(255,255,255,0.06)
--glass-edge:   rgba(255,255,255,0.22)
```

### 7.2 Typography
- **Display:** Fraunces variable (400–500), letter-spacing -0.025em at large sizes.
- **Body:** Inter variable (400, 500, 600).
- **Mono:** JetBrains Mono for scores, counts, timestamps.

Type scale: 11 / 12 / 13 / 14 / 16 / 20 / 28 / 38 / 52 / 72.

### 7.3 Spacing & Radius
- Spacing: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64.
- Radius: 8 (inputs) / 14 (chips) / 20 (cards) / 28 (panels) / 999 (pills).

### 7.4 Grain
Global fixed-position SVG turbulence layer, 14% opacity, `mix-blend-mode: overlay`, `pointer-events: none`. Survives route transitions (mounted at layout root).

### 7.5 Glass primitives

Three tiers, chosen per-surface based on performance budget:
- `glass-hero` — WebGL liquidGL instance with real refraction, chromatic dispersion, specular edge. Used on navigation bar, detail panel, chat drawer, modal sheets. Max ~6 instances per rendered page.
- `glass-card` — CSS approximation: `backdrop-filter: blur(22px) saturate(1.2)`, layered chromatic gradient via `::before`, specular top-edge via `::after`.
- `glass-chip` — lightweight: subtle blur, single inset highlight, no pseudo-elements.

### 7.6 Motion

Defined in `frontend/src/motion/presets.ts`:

```
transitions:
  page:   fade + 8px slide-up, 400ms, cubic-bezier(0.16, 1, 0.3, 1)
  modal:  scale 0.95→1 + blur 20→0, 320ms
  stagger: 30ms per child, max 8 children

spring:
  soft:   { stiffness: 260, damping: 24 }
  snap:   { stiffness: 400, damping: 28 }
  bounce: { stiffness: 180, damping: 14 }

interactive:
  button:
    hover: { scale: 1.02, y: -1 }
    tap:   { scale: 0.98 }
  card:
    hover: { y: -4, shadowGlow: amber }
  chip:
    hover: { scale: 1.04 }
    tap:   { scale: 0.96 }
```

Score numbers animate with a count-up on first paint (300ms). Lists stagger-in on mount. Chat bubbles spring-appear; typing-dots render while awaiting response.

## 8. Component Taxonomy

Directory: `frontend/src/components/`

- `glass/` — `GlassPanel`, `GlassCard`, `GlassChip`, `LiquidGLMount` (React wrapper for the library).
- `motion/` — `FadeIn`, `StaggerList`, `SpringButton`, `ScoreCountUp`.
- `anime/` — `AnimeCard`, `AnimeHero`, `StatusSelector`, `GenreChipRow`, `ScoreBlock`, `RatingSlider`.
- `chat/` — `ChatDrawer`, `ChatBubble`, `ChatSuggestionChip`, `AIAvatar`, `TypingDots`.
- `nav/` — `TopNav`, `SearchCommand`, `UserMenu`.
- `charts/` — `GenreRadar`, `Histogram`, `BarStack` (used by Stats).
- `layout/` — `AmbientScene` (blobs + grain), `Page`, `Scrollable`.
- `primitives/` — button, input, select, modal, drawer, toast, skeleton. All Framer-Motion-wrapped.

Routes live in `frontend/src/routes/`: `browse`, `for-you`, `my-list`, `anime/$id`, `stats`, `collections`, `collections/$id`, `seasonal`, `activity`, `compare`, `onboarding`, `auth`.

## 9. Feature Specs

### 9.1 Preserved features
Browse · For You · My List (5 statuses + favorites) · Anime detail (synopsis, fan genres, rating, AI-assisted rating, similar anime) · Rating (1–10 slider with color gradient) · Fan genre voting (59 tags in 5 categories) · AI Chat (tool use + mood buttons + follow-ups + interactive recommendation cards) · AniList integration (search/popular/top/trending/seasonal) · Search (autocomplete + advanced) · Onboarding (guided AI or jump-in) · Auth (register/login/profile).

### 9.2 Stats Dashboard — `/stats`
- **Header strip:** total anime rated, total ratings, total fan-genre votes, avg score, estimated hours watched.
- **Hours-watched formula:** `Σ(episode_count × assumed_length) × completion_ratio`, where completion_ratio = 1 for Completed, 0.5 for Watching/On-Hold, 0 otherwise; `assumed_length = 24 min` default, overridden by per-anime data if available.
- **Genre radar:** top 8 genres by weighted vote (vote × user_score).
- **Year distribution:** histogram by anime release year.
- **Score distribution:** histogram of user's 1–10 ratings.
- **Top studios:** bar chart, top 10.
- **Top fan tags:** chip cloud sized by personal use count.
- **Personality paragraph:** short AI-generated blurb describing the user's taste (runs the provider once, caches 24h in DB).

### 9.3 Collections — `/collections`, `/collections/$id`
- Index: grid of collection cards, each with color, icon, item count, cover mosaic of first 4 items.
- Detail: collection cover header + grid of contained anime + edit controls.
- Add flow: from any anime card/detail, "Add to collection" menu lists user's collections; single click adds.
- Public share: toggle `is_public` → generates `share_token`; view-only URL at `/share/collections/<token>`.
- Color palette: amber, violet, rose, teal, sage, cream, slate.
- Icons: a small curated set (star, bookmark, heart, flame, moon, crown, compass, tag).

### 9.4 Seasonal — `/seasonal`
- Default to current season/year (computed client-side).
- Season/year selectors in header (Winter/Spring/Summer/Fall × years 2010–current+1).
- Grid of anime cards with user's status badge overlay.
- Filters: "Airing now" · "Not on my list" · "On my list" · By genre.
- "Airing now" pulls from `/api/seasonal/airing-now`.
- Anime already in DB reuse stored records; others are fetched live from AniList and cached.

### 9.5 Activity — `/activity`
- Reverse-chronological list of user events: rated/updated-rating, tagged (added fan-genre vote), status changed, added to collection, wrote review.
- Each item: small cover thumb, action verb, anime title, timestamp (relative).
- Infinite scroll via `before=<timestamp>`.
- "On this day" callout at top (if matches exist).
- Groupings by day with sticky date headers.

### 9.6 Compare — `/compare?a=<id>&b=<id>`
- Two-column layout, each column showing: cover, title, your score + delta, AniList score, years/episodes/studio, all genres (shared highlighted), all fan genres (shared highlighted), review text.
- Top bar: "A vs B" plus icon buttons to swap or pick a different anime.
- Entry points: "Compare with…" button on anime detail page (opens picker); "Compare" button in My List (multi-select two).
- Shared sections visually bridged with a middle connector.

## 10. Migration Plan

- **Database:** existing data preserved. Two new tables created via SQLAlchemy `create_all()` on first run. No migrations framework introduced in this pass.
- **Frontend:** the existing `static/index.html` is archived to `static/_legacy-index.html` and removed from routing. Flask's catch-all serves from `static/dist/` (Vite output). Deep links to legacy hash routes (`#/anime/123`) are redirected to `/anime/123` by a small client-side bootstrap.
- **Environment:** `.env.example` is added at repo root documenting both provider configs.
- **Render:** `render.yaml` build command updated to install Node 20 and run frontend build before pip install.

## 11. Performance Strategy

- **liquidGL cap:** max 6 WebGL instances concurrently mounted per page. Beyond that, fall back to CSS glass. Enforced via a `useLiquidGLSlot()` hook that manages a global counter.
- **Code splitting:** lazy routes for stats, collections detail, compare, seasonal.
- **Images:** all covers use `loading="lazy"` and `decoding="async"`; blur-hash placeholder if AniList provides one.
- **Query cache:** TanStack Query `staleTime: 60_000` default, `5 * 60_000` for AniList-sourced queries.
- **Animation budgets:** stagger lists cap at 8 items; beyond that, switch to a simple fade.
- **Grain overlay:** static SVG data-URI, decoded once; `will-change: auto`.

## 12. Testing

- **Backend:** pytest.
  - Provider abstraction: unit tests for `OllamaProvider` and `AnthropicProvider` with mocked HTTP, verifying tool-call parsing + fallback detection.
  - New endpoints: integration tests covering collections CRUD, stats aggregation math, activity feed shape, seasonal filtering, compare normalization.
- **Frontend:** Vitest.
  - Taste-profile math, hours-watched estimator, date formatting, route guards.
- **End-to-end:** Playwright (already installed globally).
  - Flows: register → rate → see For You update → create collection → add anime → view stats.
  - Screenshot tests on: browse, anime detail, for-you, stats dashboard.
- **Visual regression:** baseline screenshots committed; diffs fail CI.

## 13. Open Questions

None blocking. The following get resolved during implementation:
- Exact tool-use protocol for `gemma4:31b` (detect at runtime; fallback path is specified).
- Final icon set for collections (curated during polish pass).
- Whether to self-host Fraunces + Inter + JetBrains Mono or use `fontsource` packages (likely fontsource for ease).

## 14. Commit & Attribution

Per owner preference, no commit message, PR description, code comment, or committed file will reference Claude, AI assistance, or any automated authorship. This includes avoiding `Co-Authored-By: Claude` trailers and any "Generated with…" footers.
