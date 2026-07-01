# Dub schedule runbook

How an episode's dub air date is determined, best source first:

1. **Crunchyroll RSS** (`sync_dub_crunchyroll.py`) — real, season-aware.
2. **AnimeSchedule.net** (`sync_dub_animeschedule.py`) — real + season-correct, the
   single biggest accuracy lever. **Needs a valid `ANIMESCHEDULE_API_KEY`** (free,
   self-serve). When missing it 401s and the dub tab falls back to estimates.
3. **Research fallback** (`POST /api/admin/ingest-dub-dates`, `dub_source=research`)
   — corroborated dates for gaps AnimeSchedule misses; the monthly
   `bingery-dub-research` scheduled task fills these.
4. **User dub reports** (`routes/dub_reports.py`) — `dub_source = user:<name>`.
5. **Synthetic fallback** (`seed_dub_schedule.py`) — for a show that already has
   real dub evidence, projects its remaining episodes at that show's learned
   median sub→dub lag. Shows with **no** dub evidence are left untouched (we don't
   invent a dub for a title that may have no English dub). Tagged
   `synthetic_lag_8w` and shown as **estimated** everywhere: schedule rows show
   "time TBD" (not a fake clock time) and the detail widget shows "expected ~<date>".

Precedence: real sources (1, 2) and user reports are never overwritten by the
research fallback or the synthetic seeder unless forced. `research` upgrades
NULL/synthetic rows and is itself preserved by the seeder (and feeds learned lag).

## ⭐ Restore real dub accuracy (do this first)

The daily sync pipeline already exists — GitHub Action
`.github/workflows/refresh-schedule.yml` (daily 06:00 UTC) plus Render cron
`bingery-dub-animeschedule`. It has been dark only because the AnimeSchedule key
is unset/expired. To fix:

1. Create a free AnimeSchedule.net account, then generate an API token at
   `https://animeschedule.net/users/<your-username>/settings/api`.
2. Set it on the live server(s):
   - **Fly:** `fly secrets set ANIMESCHEDULE_API_KEY=<token>` (also confirm
     `fly secrets set ADMIN_SYNC_SECRET=<secret>` is set).
   - **Render:** set `ANIMESCHEDULE_API_KEY` and `ADMIN_SYNC_SECRET` in the
     dashboard for the web service + the `bingery-dub-animeschedule` cron.
   - **GitHub:** repo Settings → Secrets and variables → Actions →
     `ADMIN_SYNC_SECRET` (same value as the server) so the daily Action can auth.
3. Verify: with the key in your env, `python sync_dub_animeschedule.py --dry-run`
   should report `matched > 0`. Dub dates from AnimeSchedule are NOT marked
   estimated, so they show real times in the UI.

## Trigger the sync on demand / on a schedule

The admin endpoint runs all syncs in-process on the live worker:

    curl -X POST -H "X-Admin-Secret: <secret>" https://bingery.fly.dev/api/admin/sync-dub-sources

- **Cloud (default):** the GitHub Action runs this daily at 06:00 UTC.
- **Local backup (Windows):** `refresh-dub-schedule.ps1` does the same POST.
  Set `BINGERY_ADMIN_SECRET` (and optionally `BINGERY_URL`) once:

      setx BINGERY_ADMIN_SECRET "<secret>"

  then run (or double-click `refresh-dub-schedule.cmd`):

      powershell -ExecutionPolicy Bypass -File ".\refresh-dub-schedule.ps1"

  Schedule it monthly via Task Scheduler:

      schtasks /Create /TN "Bingery dub refresh" /SC MONTHLY /D 1 /ST 09:00 ^
        /TR "\"C:\Users\parus\Downloads\bingery-update\refresh-dub-schedule.cmd\""

## Research fallback (gaps AnimeSchedule misses)

`POST /api/admin/ingest-dub-dates` accepts a batch of corroborated real dates:

    {"rows": [{"title": "Spy x Family", "episode_number": 12,
               "air_date": "2026-07-05T17:00:00Z"}],
     "dub_source": "research"}

Rows match by `anilist_id` (preferred) or fuzzy `title`. They fill NULL/synthetic
dub dates and never clobber Crunchyroll / AnimeSchedule / user rows unless you
pass `"overwrite": true`. Ingest a saved research JSON with:

    curl -X POST -H "X-Admin-Secret: <secret>" -H "Content-Type: application/json" \
      --data @dub-research/2026-07-01.json \
      https://bingery.fly.dev/api/admin/ingest-dub-dates

The monthly **`bingery-dub-research`** scheduled task (Cowork) researches these
automatically, writes `dub-research/<date>.json`, and POSTs them when
`BINGERY_ADMIN_SECRET` is set in the environment.

## Running the synthetic seeder

    python seed_dub_schedule.py            # write/refresh synthetic dubs
    python seed_dub_schedule.py --dry-run  # report counts only
    python seed_dub_schedule.py --reset    # wipe synthetic rows, then exit

The seeder's date math uses SQLite's `datetime(...)`, so it runs on the **Fly
(SQLite)** deployment — manually or via a Fly scheduled machine — not on Render.
