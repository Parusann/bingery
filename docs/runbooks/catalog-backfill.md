# Catalog backfill runbook

The catalog sync chunks AniList by `seasonYear`, so titles with
`seasonYear: null` (typically ONA / donghua) are not reached by the normal
`--full` sync. Use these tools to add them.

## Add specific titles now (targeted, cheap)

    python sync_anilist.py --ids 137667 156092

(137667 = Lord of Mysteries, 156092 = To Be Hero X. Find any title's id from
its AniList URL, e.g. anilist.co/anime/137667.)

## Backfill the whole orphan category (broad sweep)

    python sync_anilist.py --all-orphan-formats

Covers SPECIAL / OVA / ONA / MUSIC / TV_SHORT, including seasonYear-null
entries. Heavier (many pages, AniList rate limits). Run it manually when
coverage gaps appear — there is no recurring orphan job (the Render crons
that used to run it were retired 2026-07-10; new-season TV titles arrive via
the weekly seasonal pull in `.github/workflows/refresh-schedule.yml`).

## Per deployment
- **Fly** (SQLite shipped once, no cron): there is no recurring sync on Fly. To
  add titles, either run a command above against the database Fly serves and
  redeploy, or add a scheduled machine that runs the orphan-catcher. Until then
  Fly's catalog only changes when the DB is re-shipped.
