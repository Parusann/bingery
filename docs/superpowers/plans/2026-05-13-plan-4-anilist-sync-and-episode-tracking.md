# Plan 4 — Full AniList catalog sync + sub/dub episode release tracking

**Date:** 2026-05-13
**Branch (proposed):** `revamp/anilist-sync-and-schedule`
**Base:** `main` at `0081eb9` (Plan 3 merged)
**Status:** Phase A scoped, Phase B pending dub-source decision

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

# Phase B — Dub episode tracking

## **Phase B is blocked on the dub data source decision. See options below; pick one before scoping the tasks.**

## Phase B task skeleton (to be detailed once source is chosen)

- **B1.** Add `air_date_dub`, `dub_source` fields to Episode (already speced in A1 — confirms columns exist)
- **B2.** Implement the chosen data source (see options below for what this looks like per choice)
- **B3.** Extend `/api/schedule/upcoming?kind=dub` to actually return dub episodes
- **B4.** Frontend: enable "Dub" filter tab on /schedule; show dub air date on AnimeDetail's NextEpisodeWidget; optional Sub/Dub badge on Episode rows
- **B5.** Tests + verification

---

## Phase B — Dub data source options

| | Source | Coverage | Effort | Risk |
|---|---|---|---|---|
| **B-i** | Crunchyroll RSS feeds | ~70% (recent CR-distributed dubs) | Medium (parser + cron) | Medium — format undocumented, can break |
| **B-ii** | Manual user submissions | Variable — depends on community | High (moderation UX) | Low — fully under your control |
| **B-iii** | AnimeSchedule.net | ~85% (covers most dubs in single feed) | Low (single fetch) | High — semi-public API, ToS gray area |
| **B-iv** | Hybrid: CR RSS + AnimeSchedule fallback + manual fill | ~95% | Very high (three sources) | Mixed (mostly B-iii's risks) |
| **B-v** | Sub-only (defer dub to Plan 5) | 0% (dub) | Zero | Zero |

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

## Open questions

1. **Which dub source (B-i through B-v)?**
2. **Do you want Phase A to include the initial 5-hour sync run, or just ship the script and run it yourself overnight?**
3. **Is the existing 20-row seed DB worth preserving as fallback test data, or can `seed.py` be deleted entirely once sync is in place?**

## Out of scope (could be Plan 5)

- Push/email notifications when a tracked show's new episode airs
- Multi-language dub tracking beyond English (Spanish, German, French dubs)
- Episode-level user state (watched, watching, skipped) per-episode rather than per-anime
- Re-running sync from `mal_id` instead of `anilist_id` for shows where AniList has stale data
