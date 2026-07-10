# Schedule audit runbook

The schedule auditor verifies every entry `/api/schedule/week` serves — both
tracks, `air_date_sub` and `air_date_dub` — against independent sources, and
alarms when the pipeline degrades. It is **read-only by design**: the daily
cron reports and fails loudly; corrections only ever happen in attended runs
through the existing precedence machinery.

## How it verifies

Enumeration goes through `utils/schedule_window.window_rows_query` — the same
query the API route uses (margin-inclusive superset), so the audit can never
drift from the serving surface.

Sources (each an independent "voice"):

| voice            | what it answers                                | matching            |
|------------------|------------------------------------------------|---------------------|
| `anilist`        | per-episode air timestamps (batched `airingSchedules`), status, episode totals | `anilist_id` (confidence 100) |
| `myanimelist`    | status, JST broadcast weekday, episode totals — official MAL v2 with `X-MAL-CLIENT-ID`; keyless Jikan answers **as the same voice** when MAL rate-limits (they share underlying data and can never fake two-source agreement) | `mal_id` (confidence 100) |
| `animeschedule`  | dub timetable dates + dub-track liveness (needs `ANIMESCHEDULE_API_KEY`; **dark** without it) | `best_match` fuzzy, threshold 80, confidence = score |
| `crunchyroll_rss`| dub episode premieres from the RSS feed        | `best_match`, threshold 80 |
| `web_research`   | attended-only claims from a `--research-file` JSON; never set in CI | explicit `anime_id` |

A date is **CONFIRMED** when ≥2 voices agree with ours on the same UTC
calendar day (±1 day only when a side is date-only — absorbs the JST-broadcast
vs simulcast-listing offset). **MISMATCH** = ≥2 voices agree on a *different*
day (the consensus and every voice's answer are recorded), or the episode
number exceeds the confirmed episode count. **ESTIMATED** = the row is the
synthetic projection (`dub_source == "synthetic_lag_8w"`), which the UI labels
via `estimated` / `dub_estimated` and the `EstimatedTag` pill. **UNVERIFIABLE**
= fewer than two voices had data; flagged, never guessed.

Per-track status rules: a finished sub with an ongoing dub is legitimate dub
content — dub leaks require dub-track evidence (or an impossible episode
number). Future sub episodes of two-voice-confirmed finished shows are leaks.

## Thresholds (the CI gate)

| metric                      | default | rationale |
|-----------------------------|---------|-----------|
| `MISMATCH` entries          | > 5 fails | sync pipeline writing wrong dates |
| synthetic dub fraction      | > 60% fails | real dub tiers are dark (key missing/expired) |
| evidence-backed leaks       | > 0 fails | finished/nonexistent content is being served |

Overrides: `--max-mismatch`, `--max-synthetic-frac`, `--max-leaks`
(CLI, with `--fail-on-thresholds`). The admin endpoint always returns
`threshold_breaches` computed at the defaults; the workflow fails on any.

## Running it

* **Attended (deep):** `python audit_schedule.py --weeks 3 --tag <name>
  [--cache reports/schedule-audit/.http-cache.json] [--research-file r.json]`
  Writes `reports/schedule-audit/<tag>-audit.{json,md}`.
* **Admin endpoint:** `POST /api/admin/audit-schedule` with `X-Admin-Secret`,
  body `{"weeks": 1, "max_anime": 80}` (clamped 1–4 / 10–200). Read-only.
* **CI:** the `audit` job in `.github/workflows/refresh-schedule.yml` runs
  after the daily sync, uploads `audit-report.json` as an artifact (90 days),
  and on breach fails the job and opens/updates a `schedule-audit` issue.

Tier health also comes from `GET /api/admin/dub-doctor` and is attached to
every `sync-dub-sources` response under `dub_doctor`.

## Correction policy (attended only)

The cron never corrects. In an attended run:

1. **Stale statuses** (`status_stale` in the report): refresh through the
   existing AniList machinery —
   `python sync_anilist.py --ids <anilist ids from the report>`.
2. **Fabricated synthetic rows**: `python seed_dub_schedule.py --prune-ghosts`
   (dry-run first). Removes projections for finished shows with zero real dub
   evidence and rows numbered past the finale. Real-source and user-reported
   rows are never touched.
3. **High-confidence dub-date corrections** (≥2 voices against our value):
   `POST /api/admin/ingest-dub-dates` with `dub_source="research"` — upgrades
   NULL/synthetic rows only; never clobbers `crunchyroll_rss`/`animeschedule`/
   `user:*` without `overwrite: true`.

## When the synthetic fraction alarms

That means AnimeSchedule (Tier 2) is dark — almost always the missing/expired
`ANIMESCHEDULE_API_KEY`. Provision a token at animeschedule.net (account
settings → API), set it on Fly (`fly secrets set ANIMESCHEDULE_API_KEY=...`)
and on Render (`bingery-dub-animeschedule` cron), then re-run the sync and
confirm `dub_doctor` reports the tier `live`. `sync_dub_animeschedule.py`
exits with code 2 and a `TIER DARK` message when the key is absent.
