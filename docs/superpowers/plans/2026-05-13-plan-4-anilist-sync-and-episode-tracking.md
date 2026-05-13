# Plan 4 — Full AniList catalog sync + sub/dub episode release tracking

**Date:** 2026-05-13
**Branch (proposed):** `revamp/anilist-sync-and-schedule`
**Base:** `main` at `0081eb9` (Plan 3 merged)
**Status:** Phase A scoped + Phase B locked to **B-iv (Hybrid)** dub source
**seed.py decision:** Kept as-is. Documented role: fresh-DB dev bootstrap only. Production deploys do not run it. The 20 hand-curated anime will be near-duplicates of AniList rows post-sync; acceptable dev-only impact.

---

## Goals

1. **Full AniList catalog sync.** Replace the 20-row hand-curated seed with a comprehensive `Anime` table sourced from AniList. Make the sync **idempotent, paginated, resumable, rate-limited** so it can be re-run weekly to pick up updates.
2. **Sub episode release tracking.** For airing shows, surface "next episode airs in X" on detail pages and a `/schedule` page showing the next 7 days of episode drops.
3. **Dub episode release tracking.** Same UX as sub, but for English (and ideally other-language) dubs. Data source choice is the open decision — see Phase B options below.

## Pre-requisites

- Plan 3 merged to main (✅ done at `0081eb9`)
- Working dev environment: `python app.py` + `npm run dev` + seeded DB
- Optional: GitHub Actions or other cron host for scheduled re-syncs (not required for the initial implementation)

## High-level architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  AniList GraphQL API (public, 90 req/min unauthenticated)            │
└────────────────────────┬─────────────────────────────────────────────┘
                         │ paginated GraphQL queries
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  sync_anilist.py (CLI, resumable)                                    │
│  - Reads AniListSyncState for last cursor                            │
│  - Upserts Anime rows + Episode rows                                 │
│  - Writes back updated cursor + timestamps                           │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Bingery DB (SQLite dev / Postgres prod)                             │
│  - Anime (existing, fully populated)                                 │
│  - Episode (NEW: per-episode air dates, sub + dub)                   │
│  - AniListSyncState (NEW: pagination cursors, timestamps)            │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Backend API: /api/schedule/upcoming, /api/anime/<id>/episodes       │
└────────────────────────┬─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend: SchedulePage, NextEpisode widget on AnimeDetail           │
└──────────────────────────────────────────────────────────────────────┘
```

## Decisions to make before Phase B

**See "Phase B — Dub data source options" section at the bottom.** Pick one before implementing Phase B tasks. Phase A is independent and can start now.

---

# Phase A — Full sync + sub schedule (10 tasks)

## Task A1: Add Episode + AniListSyncState models

**Files:**
- Modify: `models.py`
- Modify: `tests/test_models.py` *(create if missing)*

**Schema:**

```python
class Episode(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    anime_id        = db.Column(db.Integer, db.ForeignKey("anime.id"), nullable=False, index=True)
    episode_number  = db.Column(db.Integer, nullable=False)
    air_date_sub    = db.Column(db.DateTime, nullable=True, index=True)
    air_date_dub    = db.Column(db.DateTime, nullable=True, index=True)  # Phase B
    sub_source      = db.Column(db.String(40), default="anilist")
    dub_source      = db.Column(db.String(40), nullable=True)            # Phase B
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = db.Column(db.DateTime, default=..., onupdate=...)

    __table_args__ = (db.UniqueConstraint("anime_id", "episode_number"),)

class AniListSyncState(db.Model):
    """Singleton row tracking the last successful sync state."""
    id              = db.Column(db.Integer, primary_key=True)
    last_page       = db.Column(db.Integer, default=0)
    last_run_at     = db.Column(db.DateTime, nullable=True)
    last_full_at    = db.Column(db.DateTime, nullable=True)
    total_synced    = db.Column(db.Integer, default=0)
    status          = db.Column(db.String(20), default="idle")  # idle | running | error
    error_message   = db.Column(db.Text, nullable=True)
```

**Acceptance:**
- `db.create_all()` succeeds on a fresh DB
- For existing dev DBs, ship an `ALTER TABLE` snippet in the task notes (since the project uses no migration framework)
- Episode.to_dict() emits `{id, anime_id, episode_number, air_date_sub, air_date_dub}` with ISO timestamps

---

## Task A2: AniList sync utility

**Files:**
- Modify: `utils/anilist.py` *(extend existing AniListClient)*
- Create: `sync_anilist.py` *(repo root — CLI entry point)*
- Create: `tests/test_sync_anilist.py`

**Behavior:**
- Fetches anime in pages of 50 using `Page(page, perPage)` GraphQL query
- Selects fields: `id, idMal, title{english, native, romaji}, description, averageScore, seasonYear, season, episodes, studios{nodes{name}}, coverImage{large}, bannerImage, status, source, genres, nextAiringEpisode{airingAt, episode, timeUntilAiring}, airingSchedule{nodes{episode, airingAt}}`
- Upserts to `Anime` (match by `anilist_id`) and `Episode` (match by `anime_id, episode_number`)
- Rate limit: sleep to respect 90 req/min (target 1 req/0.7s)
- Resumable: reads `AniListSyncState.last_page`, starts from there
- Idempotent: re-runs update timestamps but don't duplicate
- Logs: progress every 10 pages, totals at end
- CLI: `python sync_anilist.py [--full | --since YYYY-MM-DD | --resume]`
- Exits 0 on success, non-zero on unrecoverable error

**Acceptance:**
- Dry-run mode (`--dry-run`) prints what would be written without committing
- `python sync_anilist.py --resume` after interrupt continues from `last_page + 1`
- Tests use a mocked GraphQL client (no live network) and verify upsert + episode creation
- Real run (manual, not in CI): fetches first 5 pages successfully against live AniList

---

## Task A3: Schedule API endpoints

**Files:**
- Create: `routes/schedule.py`
- Modify: `app.py` *(register blueprint at `url_prefix="/api/schedule"`)*
- Create: `tests/test_schedule.py`

**Endpoints:**

```
GET /api/schedule/upcoming?days=7&kind=sub
  -> 200 {
       "days": [
         {
           "date": "2026-05-14",
           "episodes": [
             {
               "id": <int>,
               "episode_number": 5,
               "air_at": "2026-05-14T14:30:00Z",
               "anime": {id, title, image_url},
               "kind": "sub"   // or "dub"
             }
           ]
         },
         ...
       ]
     }
```

```
GET /api/anime/<int:anime_id>/episodes
  -> 200 {
       "episodes": [
         {id, episode_number, air_date_sub, air_date_dub},
         ...
       ],
       "next_sub": <Episode | null>,
       "next_dub": <Episode | null>
     }
```

**Acceptance:**
- `?kind=sub` (default), `?kind=dub`, or `?kind=both` (returns both with `kind` field on each)
- `?days` clamped to [1, 30], default 7
- Empty days included with `episodes: []` (so frontend renders continuous timeline)
- Auth required (JWT) — same pattern as other endpoints

---

## Task A4: Frontend types + API client + hook

**Files:**
- Modify: `frontend/src/types/models.ts` *(append Episode, ScheduleDay, ScheduleResponse)*
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts` *(add `getSchedule`, `getAnimeEpisodes`)*
- Create: `frontend/src/hooks/useSchedule.ts`

**Types:**

```ts
export interface Episode {
  id: number;
  episode_number: number;
  air_date_sub: string | null;
  air_date_dub: string | null;
}

export interface ScheduleEpisode {
  id: number;
  episode_number: number;
  air_at: string;
  anime: AnimeSummary;
  kind: "sub" | "dub";
}

export interface ScheduleDay {
  date: string;
  episodes: ScheduleEpisode[];
}

export interface ScheduleResponse {
  days: ScheduleDay[];
}
```

**Hooks:**
- `useSchedule(days = 7, kind: "sub" | "dub" | "both" = "sub")` → query
- `useAnimeEpisodes(animeId)` → query

---

## Task A5: SchedulePage component

**Files:**
- Create: `frontend/src/features/schedule/ScheduleCalendar.tsx` *(day-strip layout)*
- Create: `frontend/src/features/schedule/ScheduleEpisodeRow.tsx` *(single row: thumb + title + time + ep number)*
- Create: `frontend/src/features/schedule/SchedulePage.tsx`

**UX:**
- Top: title "Upcoming episodes" + filter tabs (Sub / Dub / Both)
- Body: vertical list of days. Each day card has the date header + episode rows
- Empty days show a quiet "No releases scheduled."
- Loading: skeleton rows
- Sub-only initially; "Dub" tab disabled until Phase B ships (or shows a "Coming soon" notice)

---

## Task A6: NextEpisode widget on AnimeDetail

**Files:**
- Create: `frontend/src/features/anime/NextEpisodeWidget.tsx`
- Modify: `frontend/src/features/anime/AnimeDetailPage.tsx` *(add the widget below DetailHero)*

**UX:**
- Pill-style widget: "📺 Episode 5 (sub) airs in 2d 14h" with relative + absolute timestamp tooltip
- Both sub and dub badges if both data exist
- Hidden for completed shows (no next episode)

---

## Task A7: Routes + NavBar

**Files:**
- Modify: `frontend/src/routes.tsx` *(add `/schedule` lazy route)*
- Modify: `frontend/src/layout/NavBar.tsx` *(add "Schedule" link)*

---

## Task A8: Backend + frontend tests

**Backend (`tests/test_schedule.py`):**
- `/api/schedule/upcoming` returns days in order, no duplicates
- `?kind=sub|dub|both` filters correctly
- `?days` clamping (0, 100 → clamp to 1, 30)
- Auth required
- Empty-DB edge case returns all days with empty arrays
- Per-anime episodes endpoint: returns episodes sorted by number; `next_sub`/`next_dub` correct

**Frontend (vitest):**
- SchedulePage renders skeleton during load
- SchedulePage renders empty-state message when no episodes
- NextEpisodeWidget shows relative time correctly (mock Date.now)
- NextEpisodeWidget hidden when no airing data

---

## Task A9: First sync run + verification

**Files:** none (operational task)

**Steps:**
1. Stop Flask
2. Backup current `bingery.db` to `bingery.db.bak`
3. Run `python sync_anilist.py --full --dry-run | head -50` to sanity-check
4. Run `python sync_anilist.py --full` — **expect ~5 hours wall clock**
5. Monitor every ~30 min: tail logs, check `AniListSyncState.last_page` is advancing
6. After completion: verify `SELECT COUNT(*) FROM anime` is >20,000; `SELECT COUNT(*) FROM episode WHERE air_date_sub IS NOT NULL` is non-zero
7. Restart Flask + Vite
8. Smoke test in browser: /discover shows many anime; /schedule shows upcoming sub releases

**Acceptance:**
- DB has ~25,000 anime rows
- At least 50 anime with `nextAiringEpisode` populated
- /schedule shows non-empty upcoming list for current week
- Existing demo users + their ratings unchanged

---

## Task A10: Scheduled re-sync (cron-ready) — optional but recommended

**Files:**
- Create: `.github/workflows/anilist-resync.yml` *(or render.com cron config — see render.yaml)*

**Behavior:**
- Runs weekly (e.g. every Sunday 03:00 UTC)
- Executes `python sync_anilist.py --resume`
- Only re-pulls anime whose `updated_at` is older than 7 days (efficient incremental)

---

# Phase B — Hybrid dub episode tracking (chosen path: B-iv)

## Architecture: tiered fallback

Three data sources, written to `Episode.air_date_dub` with `dub_source` indicating which one filled it:

```
┌─────────────────────────────────────────────────────────────────┐
│ Tier 1 — Crunchyroll RSS (automated, ~70% coverage)            │
│   - Cron-pulls https://feeds.feedburner.com/crunchyroll/rss    │
│   - Fuzzy-match RSS title → Anime row by title/anilist_id      │
│   - Sets dub_source = "crunchyroll_rss"                        │
└─────────────────────────────────────────────────────────────────┘
                              │ writes
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Tier 2 — AnimeSchedule.net API (automated, fills gaps to ~95%) │
│   - Cron-pulls /api/v3/timetables/dub                          │
│   - Only updates Episode rows where dub_source is null         │
│   - Sets dub_source = "animeschedule"                          │
└─────────────────────────────────────────────────────────────────┘
                              │ writes (gaps only)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Tier 3 — Manual user submissions (community-curated, edge cases)│
│   - DubReport endpoint + minimal moderation queue              │
│   - Verified submissions override Tier 1/2 if more recent      │
│   - Sets dub_source = "user:<username>"                        │
└─────────────────────────────────────────────────────────────────┘
```

## Phase B tasks

### Task B1: Episode.air_date_dub schema confirmation + DubReport model

**Files:**
- Modify: `models.py` *(add `DubReport` model)*
- Modify: `tests/test_models.py`

**DubReport model:**

```python
class DubReport(db.Model):
    """User-submitted dub air-date submissions, awaiting moderation or auto-accepted."""
    id              = db.Column(db.Integer, primary_key=True)
    episode_id      = db.Column(db.Integer, db.ForeignKey("episode.id"), nullable=False, index=True)
    submitted_by    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    air_date        = db.Column(db.DateTime, nullable=False)
    status          = db.Column(db.String(20), default="pending")  # pending | accepted | rejected
    note            = db.Column(db.String(500), nullable=True)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at     = db.Column(db.DateTime, nullable=True)
    reviewed_by     = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
```

**Acceptance:**
- `Episode.air_date_dub` + `dub_source` columns exist (from Task A1)
- `DubReport` table created via `db.create_all()` or ALTER snippet
- Foreign-key cascade: deleting an anime cascades to its episodes and their reports

---

### Task B2a: Crunchyroll RSS ingester (Tier 1)

**Files:**
- Create: `utils/dub_sources/crunchyroll.py`
- Create: `sync_dub_crunchyroll.py` *(CLI entry, similar to sync_anilist.py)*
- Create: `tests/test_dub_crunchyroll.py`

**Behavior:**
- Fetches `https://feeds.feedburner.com/crunchyroll/rss` (or per-language variants)
- Parses each entry: extract `<title>`, `<pubDate>`, episode number from title text (regex `Episode (\d+)` etc.)
- Fuzzy-matches show title against `Anime.title` and `Anime.title_english` (token-set ratio ≥ 80%)
- If match: upsert `Episode` row, set `air_date_dub` and `dub_source = "crunchyroll_rss"`
- If no match: log to `tests/.unmatched_dub_titles.log` for manual review (also useful as a B-iii fallback signal)
- Rate-limit: 1 fetch per 60s (RSS doesn't need fast polling)
- CLI: `python sync_dub_crunchyroll.py [--dry-run | --since YYYY-MM-DD]`

**Acceptance:**
- Test against a captured RSS fixture (don't hit live URL in tests)
- Fuzzy-match correctness on edge cases (subtitles, season suffixes, romaji vs English)
- Idempotent: re-runs don't create duplicate Episodes

---

### Task B2b: AnimeSchedule.net ingester (Tier 2)

**Files:**
- Create: `utils/dub_sources/animeschedule.py`
- Create: `sync_dub_animeschedule.py` *(CLI entry)*
- Create: `tests/test_dub_animeschedule.py`

**Behavior:**
- Fetches `https://animeschedule.net/api/v3/timetables/dub` (semi-public JSON endpoint)
- For each row: match by `animeschedule.title` → `Anime.title` (same fuzzy logic as B2a)
- **Only writes `air_date_dub` if it is currently NULL** (Tier 1 takes precedence)
- Sets `dub_source = "animeschedule"`
- Graceful 4xx/5xx handling — log + exit non-zero, don't corrupt DB
- CLI: `python sync_dub_animeschedule.py [--dry-run]`

**Acceptance:**
- Test against a captured fixture
- Confirms Tier 1 data is never overwritten
- Logs how many gaps were filled vs already-populated

---

### Task B3: User dub-report endpoints (Tier 3)

**Files:**
- Create: `routes/dub_reports.py`
- Modify: `app.py` *(register blueprint at `/api/dub-reports`)*
- Create: `tests/test_dub_reports.py`

**Endpoints:**

```
POST /api/dub-reports
  body: { episode_id: <int>, air_date: "YYYY-MM-DDTHH:MM:SSZ", note?: <str> }
  -> 201 { report: {...} }
  -> 400 if episode doesn't exist or air_date is invalid
  -> 409 if same user already submitted for this episode (one report per user per episode)

GET /api/dub-reports?status=pending
  -> 200 { reports: [...] }
  (Admin-only — define is_admin flag or accept first-user-as-admin pattern for now)

PATCH /api/dub-reports/<id>
  body: { status: "accepted" | "rejected" }
  -> 200 { report: {...} }
  - If accepted: set Episode.air_date_dub = report.air_date, Episode.dub_source = "user:<username>"
```

**Acceptance:**
- A regular user can submit; only flagged admin user can accept/reject
- Accepting a report overrides existing dub data (regardless of Tier)
- Activity feed gets a new event kind `dub_report` (extend `ActivityKind` in Plan 3's frontend types)

---

### Task B4: /api/schedule/upcoming serves dub episodes

**Files:**
- Modify: `routes/schedule.py` *(extend to handle `?kind=dub`)*
- Modify: `tests/test_schedule.py`

**Behavior:**
- `?kind=dub` returns `Episode` rows where `air_date_dub` falls in the date window, sorted ascending
- `?kind=both` returns both kinds in one merged stream, each with `kind: "sub" | "dub"`
- The endpoint shape is the same as Phase A (Task A3); only the filter changes

---

### Task B5: Frontend dub UX

**Files:**
- Modify: `frontend/src/features/schedule/SchedulePage.tsx` *(enable Dub tab)*
- Modify: `frontend/src/features/anime/NextEpisodeWidget.tsx` *(show both sub + dub badges if available)*
- Create: `frontend/src/features/anime/DubReportButton.tsx` *(report-a-dub-date dialog)*
- Modify: `frontend/src/features/anime/AnimeDetailPage.tsx` *(thread in DubReportButton)*
- Create: `frontend/src/features/admin/DubReportsQueue.tsx` *(admin moderation page)*

**Acceptance:**
- /schedule "Dub" tab now lists dub episodes
- AnimeDetail shows `📺 Episode 5 sub airs in 2d` and (separately) `🇺🇸 Episode 5 dub airs in 5d`
- "Report missing dub date" button on AnimeDetail opens a small dialog (episode picker, date input, optional note)
- Admin page shows pending reports; accept/reject buttons update Episode

---

### Task B6: Scheduled re-syncs for dub sources

**Files:**
- Modify: `.github/workflows/anilist-resync.yml` *(if Task A10 shipped)* OR `render.yaml` cron job
- Add jobs:
  - `sync_dub_crunchyroll.py` — every 6 hours
  - `sync_dub_animeschedule.py` — every 24 hours
  - `sync_anilist.py --resume` — weekly (already in Task A10)

---

### Task B7: Tests + verification

- `tests/test_dub_crunchyroll.py` — captured-fixture parsing, fuzzy match, idempotency
- `tests/test_dub_animeschedule.py` — captured-fixture parsing, Tier 1 precedence
- `tests/test_dub_reports.py` — submission, dedup, moderation flow
- Manual: run all three ingesters against live data; verify /schedule "Dub" tab renders sensible data
- Manual: submit a dub report as a non-admin user, accept it as admin, verify Episode.air_date_dub updated

---

## Phase B — Dub data source options (decision: **B-iv chosen**)

| | Source | Coverage | Effort | Risk | Status |
|---|---|---|---|---|---|
| **B-i** | Crunchyroll RSS feeds | ~70% (recent CR-distributed dubs) | Medium (parser + cron) | Medium — format undocumented, can break | ✅ Used as Tier 1 in B-iv |
| **B-ii** | Manual user submissions | Variable — depends on community | High (moderation UX) | Low — fully under your control | ✅ Used as Tier 3 in B-iv |
| **B-iii** | AnimeSchedule.net | ~85% (covers most dubs in single feed) | Low (single fetch) | High — semi-public API, ToS gray area | ✅ Used as Tier 2 in B-iv |
| **B-iv** | **Hybrid: CR RSS + AnimeSchedule fallback + manual fill** | **~95%** | **Very high (three sources)** | **Mixed** | **🎯 CHOSEN** |
| **B-v** | Sub-only (defer dub to Plan 5) | 0% (dub) | Zero | Zero | ❌ Rejected |

### B-i: Crunchyroll RSS feeds (recommended for ethical clarity + automation)

- Implementation: parse Crunchyroll's public RSS feed at `https://feeds.feedburner.com/crunchyroll/rss` for newly released dubbed episodes
- Matching: fuzzy-match the episode title in the RSS feed back to an `Anime` row by title/AniList ID
- Pros: Public RSS, no auth, real-time, covers most modern dubs since CR/Funi merger
- Cons: Format breaks when CR redesigns (rare but happens); pre-2022 Funimation legacy dubs missing
- Suitable when: you want automated dub tracking with minimal user friction

### B-ii: Manual user submissions

- Implementation: new `DubRelease` model + endpoints for authenticated users to submit dates; admin-style moderation queue (flag a high-trust user role)
- Pros: 100% reliable for what's there; no external API risk; builds community
- Cons: Cold-start problem (zero data on day 1); moderation overhead; coverage depends on engagement
- Suitable when: you have a passionate user base willing to contribute, or you accept slow ramp-up

### B-iii: AnimeSchedule.net

- Implementation: GET their `/api/v3/timetables/dub` (semi-documented JSON API)
- Pros: One source covers most major dubs in structured form
- Cons: ToS unclear; API access could be revoked; rate limits unclear; not officially blessed
- Suitable when: you want fastest coverage and accept potential future breakage

### B-iv: Hybrid (CR RSS + AnimeSchedule + manual)

- Implementation: tiered fallback — CR RSS for current season, AnimeSchedule for older / non-CR titles, manual entry for gaps
- Pros: Highest coverage (~95%)
- Cons: Three pipelines to maintain; multi-source data quality reconciliation; biggest implementation
- Suitable when: production-quality coverage matters more than implementation simplicity

### B-v: Sub-only, defer dub

- Implementation: ship Phase A as-is, leave `air_date_dub` columns null forever (until Plan 5)
- Pros: Zero added risk/complexity; ships fastest; doesn't make promises you can't keep
- Cons: Doesn't deliver the dub-tracking feature you asked for
- Suitable when: you want to evaluate sub-only UX first and revisit dub later with more market intel

---

## Open questions (resolved)

1. ~~Which dub source?~~ **B-iv (Hybrid: CR RSS + AnimeSchedule + manual)**
2. ~~5-hour sync run during session?~~ **User will run it overnight on their dev machine. Runbook in Task A9 below.**
3. ~~seed.py role?~~ **Kept as-is. Documented as fresh-DB dev bootstrap only. Production deploys do not run it.**

## Out of scope (could be Plan 5)

- Push/email notifications when a tracked show's new episode airs
- Multi-language dub tracking beyond English (Spanish, German, French dubs)
- Episode-level user state (watched, watching, skipped) per-episode rather than per-anime
- Re-running sync from `mal_id` instead of `anilist_id` for shows where AniList has stale data
