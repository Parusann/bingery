# Catalog Coverage (Missing Shows) — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/catalog-coverage`

## Problem

From the fix list:

> Some popular shows missing, example Lord of Mysteries, To Be Hero X.

## Confirmed root cause (verified against AniList)

A live AniList query for both titles returns:

- **Lord of Mysteries** — `id=137667`, `format=ONA`, **`seasonYear=null`**, `countryOfOrigin=CN`, `FINISHED`, popularity ~104k.
- **To Be Hero X** — `id=156092`, `format=ONA`, **`seasonYear=null`**, `countryOfOrigin=CN`, `FINISHED`, popularity ~118k.

The catalog sync (`sync_anilist.py`) chunks the AniList catalog by `seasonYear` (1960→current+1) using `CATALOG_QUERY` (`media(type: ANIME, sort: ID, seasonYear: $seasonYear)`). Entries with `seasonYear=null` are **structurally unreachable** by that query — the code already documents this as a known coverage gap (`utils/anilist.py:179-181`). Both missing titles are exactly that case (popular ONA donghua with no `seasonYear`).

There is **no** donghua/country/format/popularity exclusion filter anywhere — so the cause is a coverage gap, not a filter. The fix already exists in the codebase but is **never scheduled**: `sync_anilist.py --all-orphan-formats` paginates by `format` (`CATALOG_QUERY_BY_FORMAT` = `media(type: ANIME, sort: ID, format: $format)`, no `seasonYear`) over `ORPHAN_FORMATS = ("SPECIAL", "OVA", "ONA", "MUSIC", "TV_SHORT")` — which reaches `seasonYear=null` ONA entries. No cron runs it (render.yaml only runs `--full`; Fly runs no cron at all).

## Goals

1. Get the named titles (and other `seasonYear=null` ONA/donghua) into the catalog.
2. Keep that category covered going forward, so popular donghua/ONA don't silently fall through again.

## Decisions (confirmed with product owner)

- Scope = **targeted backfill tool + schedule the orphan-catcher** (no live-AniList search fallback this round).
- Which deploy serves the catalog is **unknown** → design must cover both Render and Fly and clearly flag the ops steps.

## Non-goals (YAGNI)

- Live-AniList fallback in `routes/search.py` (auto-ingest on a DB miss).
- Removing or replacing the `seasonYear` chunker (it works for the 99% case).
- Any country/format/popularity ingestion filter.
- An admin UI for catalog management.

## Approach

Two complementary pieces:

1. **Targeted backfill** — a new `--ids` flag on `sync_anilist.py` to sync specific AniList IDs precisely and cheaply (vs. a full multi-format sweep). `python sync_anilist.py --ids 137667 156092` ingests the two named titles in two API calls. Reusable for any future "add this specific show" request; idempotent (upsert).
2. **Recurring coverage** — schedule `--all-orphan-formats` as a weekly cron in `render.yaml` so `seasonYear=null` ONA/donghua are ingested on an ongoing basis.

Rejected alternative: schedule the orphan sweep only and run it once for backfill — simpler but provides no precise per-title tool and makes "add one show" a slow full sweep.

## Components

### `--ids` flag (`sync_anilist.py`)
- Add an argparse option `--ids` accepting one or more integers (AniList media IDs), mutually exclusive with the other mode flags as appropriate.
- For each id: fetch the Media by id from AniList and upsert it into the DB, reusing the **existing** fetch-by-id + persist path (the same one `GET /api/anilist/anime/<id>` and the other sync modes use — `AniListClient` fetch + `sync_anime_to_db`/normalize). Do not re-implement normalization.
- Run inside the app context the way the existing orphan branch does (`create_app()` / `app.app_context()`), so DB writes work identically.
- Log per id: added / updated / not-found / error; exit non-zero only on hard failure, not on a single not-found id.

### `render.yaml` — recurring orphan-catcher cron
- Add a cron job (weekly, offset from the existing `bingery-anilist-resync` so they don't overlap) running `python sync_anilist.py --all-orphan-formats`.
- Mirror the existing resync job's env/build config (same service shape).

### Regression guard (test)
- A test asserting `ORPHAN_FORMATS` includes `"ONA"` and that `CATALOG_QUERY_BY_FORMAT` contains no `seasonYear` token — so a future "optimization" can't silently reopen the gap that hides donghua.

### Backfill runbook (docs)
- A short doc section (in the plan / a `docs` note) with the exact commands to populate the **live** catalog now, for both deploys, since which is live is unknown:
  - **Render** (Postgres + cron): run the `--ids` command as a one-off job (or trigger the new orphan cron once).
  - **Fly** (SQLite shipped once, no cron): either run `--ids` against the shipped DB before the next deploy, or add a scheduled machine. Flag that Fly has no recurring sync today, so without one of these its catalog stays static.

## Testing

- **`--ids` unit test**: with the AniList client mocked to return a known Media payload for an id, running the `--ids` path fetches that id and upserts an `Anime` row (and a second run is idempotent — no duplicate). A not-found id is logged and skipped without crashing.
- **Regression guard test**: `ORPHAN_FORMATS` contains `"ONA"`; `CATALOG_QUERY_BY_FORMAT` has no `seasonYear`.
- Full `pytest` suite stays green (the change is additive — a new flag + a new cron entry).

## Rollout / risk

- Low. `--ids` is additive (a new code path that reuses existing fetch/upsert); the cron entry is config. No schema change, no change to the existing `--full` path.
- The named titles only appear in production after the backfill command is actually run against the live DB — an ops step, called out in the runbook. The recurring cron prevents recurrence on Render; Fly needs an explicit ops decision (flagged).
- The orphan sweep is heavier than the year-chunked sync (more pages, AniList rate limits) but runs weekly and off-peak; acceptable.
