# Schedule Freshness & Variety (Sub-project A) — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/schedule-freshness`

## Context

This is sub-project **A of 4** for the schedule-accuracy fix-list item. The four
were decomposed as: **A. Freshness & variety** (this doc), B. Correct sub episode
numbers, C. Season-aware identity, D. Dub estimate accuracy. A is first because
it is the lowest-risk, hits the most-noticed complaint ("lack of variety"), and
includes a couple of quick accuracy bug-fixes.

## Problem

From the fix list, schedule complaints include "lack of variety" (too few shows)
and episodes appearing on the wrong day / missing. Two concrete root causes are
in A's scope; the wrong-season and wrong-episode-number causes are B/C/D.

## Goals

1. Episodes appear on the **correct day** for the viewer (fix the UTC-vs-local
   day-bucket bug).
2. The schedule stays **populated** (fresher airing data), addressing sparsity.
3. The "estimated" dub tag tells the **truth** about how dates are derived.

## Current state (verified; file:line)

- **Day-bucket mismatch.** The frontend computes the week anchor as the **local**
  Sunday (`frontend/src/features/schedule/utils.ts` `getSundayOfWeek`) and sends
  `?week=YYYY-MM-DD`. The backend `/api/schedule/week` (`routes/schedule.py`
  ~274+) buckets each episode by its **UTC** calendar date
  (`air_at.date().isoformat()`, with `_episode_air_date` treating naive datetimes
  as UTC). So an episode airing late-evening local can fall into the adjacent UTC
  day — it shows on the wrong day or seems to vanish from the local week.
- **Freshness.** The only AniList resync is a **weekly** Render cron
  (`render.yaml` `bingery-anilist-resync`, `"0 3 * * 0"`). **Fly runs no cron**
  (fly.toml/Procfile run only the web process). Episodes only exist when AniList
  returns `airingSchedule`/`nextAiringEpisode`, so without a frequent refresh the
  forward weeks empty out — a driver of "lack of variety."
- **Misleading copy.** `frontend/src/features/schedule/EstimatedTag.tsx` presents
  synthetic dub dates as based on "previous release cadence," but they are a flat
  ~8-week (`synthetic_lag_8w`) placeholder.

## Non-goals (handled in later sub-projects)

- Episode-number normalization / "S2 E1" labels — **B**.
- Season-aware identity & dub matching (wrong season shown) — **C**.
- Real dub estimation / restoring AnimeSchedule.net — **D**.
- Changing the NSFW filter behavior.

## Approach & components

### 1. Timezone-aware day bucketing (the wrong-day fix)
- **Frontend:** the schedule week request adds `&tz=<IANA>` using
  `Intl.DateTimeFormat().resolvedOptions().timeZone` (the hook that builds the
  `/api/schedule/week` query — `useScheduleWeek`). No other frontend change is
  needed: day labels are rendered from the returned date keys (pure dates) and
  times already render in local time, so once the keys are local-correct,
  everything aligns.
- **Backend:** `/api/schedule/week` accepts an optional `tz` param. It resolves
  it with `zoneinfo.ZoneInfo(tz)`; on missing/invalid tz it falls back to UTC
  (current behavior). Each episode's UTC air datetime is converted to that tz and
  bucketed by the **local** date; the 7 day-keys are `week_start + i days`
  (already the local Sunday the frontend sent). The DB range query keeps a small
  guard margin (query `[week_start-1d, week_end+1d)` in UTC, then bucket precisely
  by local date) so episodes near the week edges in the viewer's tz aren't
  dropped by a UTC-window query.
- Apply the same `tz` handling to the legacy `/api/schedule/upcoming` day
  bucketing only if it shares the helper; otherwise leave it (out of scope).

### 2. Freshness cron
- Add a new **`--airing`** mode to `sync_anilist.py`: query AniList for
  currently-`RELEASING` anime (a bounded set, paginated by `status: RELEASING`,
  sorted by popularity) and upsert each via the existing `process_media_entry`
  path so their `airingSchedule`/`nextAiringEpisode` stay current. This is a
  cheap, bounded job (vs. the weekly `--full` catalog walk).
- Add a **daily** cron to `render.yaml` (`bingery-anilist-airing`, `"0 6 * * *"`,
  offset from the other jobs) running `python sync_anilist.py --airing`. Mirror
  the existing cron job's `envVars` block.
- **Document the Fly gap** in the catalog/ops runbook (Fly has no cron; needs a
  scheduled machine or manual run) — same approach as the catalog PR, since which
  deploy is live is still unconfirmed. No Fly scheduler is built this round.

### 3. Honest estimated-tag copy
- Update `EstimatedTag.tsx` copy to state the dub date is an approximate
  placeholder (~8 weeks after sub), not a per-show cadence estimate. (The real
  estimation fix is D.)

## Testing

- **Backend** (`tests/test_schedule_week.py` or `tests/test_schedule.py`): an
  episode with a UTC air time just after midnight (e.g. `2026-06-17T02:30:00Z`)
  is bucketed into the **previous** local day for a negative-offset tz
  (`tz=America/Toronto`) and into the UTC day when `tz` is absent; an invalid tz
  string falls back to UTC without error.
- The currently-releasing refresh path has a unit test driven by a mocked
  AniList client (mirrors the existing `sync_anilist` tests) asserting it upserts
  airing episodes for a `RELEASING` title.
- Existing schedule tests stay green; frontend build clean.

## Rollout / risk

- Low–medium. The tz bucketing is additive (defaults to today's UTC behavior when
  `tz` is absent), so old clients are unaffected. The cron is config; the Fly gap
  is documented, not silently assumed fixed. No schema change in A (B introduces
  the schema work).
