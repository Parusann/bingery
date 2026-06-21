# Dub Date Estimation (Sub-project D) — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/schedule-dub-estimates`

## Context

Final schedule-accuracy sub-project. A = freshness (PR #12); B+C = season-aware
dub matching (PR #13, which already fixed the stated "dub episode numbers wrong"
complaint by attaching dub feed entries to the correct season's row). D addresses
the remaining dub **date** accuracy: the synthetic fallback's flat 56-day guess.

## Problem

When no real dub date exists for an episode, `seed_dub_schedule.py` projects
`air_date_dub = air_date_sub + 56 days` (`LAG_DAYS = 56`, tag `SYNTHETIC_TAG =
"synthetic_lag_8w"`) for every episode of a top-cohort airing anime. A flat
8-week lag is wrong for most shows (simulcast dubs are often same-week to a few
weeks). The synthetic seeder also runs on **no cron** (manual only), so the dub
tab goes stale. The genuinely accurate source (AnimeSchedule.net) is dead — its
API key 401s — but that is an **ops** fix, not code.

## Goals

1. Replace the flat per-show lag with each show's **observed** sub→dub lag where
   we have real dub data, falling back to the default otherwise.
2. Keep the dub tab populated by documenting how/where the seeder runs (it is
   SQLite/Fly-only).
3. Document the real long-term fix (restore the AnimeSchedule.net key).

## Current state (verified; `seed_dub_schedule.py`)

- `LAG_DAYS = 56`, `SYNTHETIC_TAG = "synthetic_lag_8w"`,
  `_REAL_DUB_SOURCES = {"crunchyroll_rss", "animeschedule"}` (user reports use
  `dub_source` like `user:<name>`).
- For each anime in the cohort (top-N by `api_score` + recently-airing), each sub
  episode lacking a dub date (or with `--overwrite`, except real sources) gets
  `air_date_dub = air_date_sub + timedelta(days=LAG_DAYS)`, `dub_source =
  SYNTHETIC_TAG`. Idempotent; never overwrites real-source dub dates.
- `render.yaml` has dub crons for Crunchyroll + AnimeSchedule, but **none** for
  the synthetic seeder.
- `routes/schedule.py` flags `estimated = (kind == "dub" and dub_source ==
  SYNTHETIC_TAG)`.

## Non-goals

- Restoring the AnimeSchedule.net API key (ops — documented, not coded).
- Season/episode-number matching (done in PR #13).
- Replacing the dub pipeline or the synthetic cohort-selection logic.
- A new `estimated`-tag variant (learned and default projections stay
  `SYNTHETIC_TAG` — both are estimates and keep the "estimated" badge).

## Approach & components

### 1. Learned per-show lag (`seed_dub_schedule.py`)
- Add `_learned_lag_days(anime_episodes) -> Optional[int]`: from the anime's
  episodes that have **both** `air_date_sub` and a **real** `air_date_dub`
  (`dub_source` set and `!= SYNTHETIC_TAG`), compute the integer **median** of
  `(air_date_dub - air_date_sub).days`. Return `None` if there are none.
- In the projection loop, compute the show's lag once per anime:
  `lag = learned if learned is not None else LAG_DAYS`, and project
  `air_date_dub = air_date_sub + timedelta(days=lag)`. Everything else
  (cohort selection, idempotency, real-source protection, `SYNTHETIC_TAG`,
  `--overwrite`/`--dry-run`/`--reset`) is unchanged.
- Median (not mean) so one outlier (a delayed episode, a same-day special)
  doesn't skew the projection.

### 2. Where the seeder runs (Fly, not Render)
- **Correction from the approved sketch:** the seeder's date math uses SQLite's
  `func.datetime(col, '+N days')`, so it is **SQLite-specific** and cannot run on
  Render's Postgres. We therefore do **not** add a Render cron (it would error).
  Instead the runbook documents running it on the **Fly** (SQLite) deploy —
  manually or via a Fly scheduled machine. Render's dub data comes from the
  existing Crunchyroll/AnimeSchedule crons + user reports. (Making the projector
  Postgres-portable is a larger, separate effort and out of scope.)

### 3. Ops runbook (`docs/runbooks/dub-schedule.md`)
- Document the dub-date pipeline (Crunchyroll RSS → AnimeSchedule.net → user
  reports → synthetic learned/default) and that **restoring
  `ANIMESCHEDULE_API_KEY`** (currently 401) is the real accuracy fix, outside
  code. Note the synthetic seeder is SQLite-specific — it runs on Fly (manual or
  a Fly scheduled machine), not on Render.

## Testing

- `_learned_lag_days` unit tests: a set of episodes with two real dub points at
  +14 and +16 days → returns `15` (median); episodes with only synthetic/no dub
  data → returns `None`.
- Integration (with `app`/`db`): a show with one real dub episode at +21 days and
  other sub-only episodes → after the seeder runs, the sub-only episodes get
  `air_date_dub = air_date_sub + 21 days` (learned), tagged `SYNTHETIC_TAG`, and
  the real-source episode is untouched. A show with no real dub data → projects
  at the 56-day default.
- Existing `seed_dub_schedule` / schedule tests stay green; full suite green.

## Rollout / risk

Low. The change is contained to the synthetic projector's per-show lag; behavior
is identical for shows without real dub data (still 56 days). No schema change.
The new cron is config. The accuracy ceiling is still bounded by AnimeSchedule
being offline — explicitly documented as the ops follow-up.
