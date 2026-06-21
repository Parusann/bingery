# Dub Date Estimation (Sub-project D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the synthetic projector's flat 56-day dub lag with each show's observed sub→dub lag where real dub data exists, and document where the (SQLite-only) seeder runs.

**Architecture:** `seed_dub_schedule.py` computes a per-show median lag from episodes that already have a real dub date, then projects each show's remaining episodes at its own lag (default 56 only for shows with no real dub data). Per-show SQL UPDATEs keep it OOM-safe (no row hydration beyond the sparse real-dub rows).

**Tech Stack:** Python, SQLAlchemy (SQLite — `func.datetime`), pytest.

Spec: `docs/superpowers/specs/2026-06-18-schedule-dub-estimates-design.md`
Branch: `feat/schedule-dub-estimates`

**Conventions:** NO AI attribution in commits. SQLite-only (matches existing seeder). Edit via desktop-commander.

---

## Verified facts (`seed_dub_schedule.py`)
- `LAG_DAYS = 56`, `SYNTHETIC_TAG = "synthetic_lag_8w"`, `_REAL_DUB_SOURCES = {"crunchyroll_rss","animeschedule"}` (user reports = `dub_source like "user:%"`).
- `preserve_clause = or_(dub_source.in_(_REAL_DUB_SOURCES), dub_source.like("user:%"))`.
- The projector does a single bulk `update(Episode).where(*eligible_clauses).values(air_date_dub=sa_func.datetime(Episode.air_date_sub, f"+{LAG_DAYS} days"), dub_source=SYNTHETIC_TAG)` (SQLite `datetime`), then prints + verifies. `eligible_clauses` = `[anime_id.in_(anime_ids), air_date_sub.isnot(None), ~preserve_clause]` (+ `air_date_dub.is_(None)` unless `--overwrite`). `dry_run` returns before the UPDATE.
- Conftest test DB is SQLite (`sqlite:///:memory:`), so `func.datetime` works in tests.

---

## Task 1: Learned per-show lag

**Files:** `seed_dub_schedule.py`; test `tests/test_seed_dub_schedule.py` (new)

- [ ] **Step 1: Write failing tests** — create `tests/test_seed_dub_schedule.py`:
  ```python
  """Tests for seed_dub_schedule.py learned-lag projection."""
  from datetime import datetime, timedelta

  from models import db, Anime, Episode
  from seed_dub_schedule import _learned_lag_days, SYNTHETIC_TAG, LAG_DAYS, main


  def test_learned_lag_days_median():
      assert _learned_lag_days([14, 16]) == 15
      assert _learned_lag_days([10, 20, 21]) == 20
      assert _learned_lag_days([]) is None


  def _airing_anime(title, score=9.0):
      return Anime(title=title, api_score=score, status="Currently Airing")


  def test_seeder_uses_learned_lag_for_partially_dubbed_show(app):
      with app.app_context():
          a = _airing_anime("Learned Show")
          db.session.add(a)
          db.session.flush()
          # Episode 1 has a REAL dub 21 days after sub.
          db.session.add(Episode(
              anime_id=a.id, episode_number=1,
              air_date_sub=datetime(2026, 1, 1), air_date_dub=datetime(2026, 1, 22),
              dub_source="crunchyroll_rss",
          ))
          # Episode 2 has only a sub date -> should be projected at +21d (learned).
          db.session.add(Episode(
              anime_id=a.id, episode_number=2,
              air_date_sub=datetime(2026, 1, 8),
          ))
          db.session.commit()
          aid = a.id

      main([])  # run the seeder

      with app.app_context():
          ep2 = Episode.query.filter_by(anime_id=aid, episode_number=2).first()
          assert ep2.dub_source == SYNTHETIC_TAG
          assert ep2.air_date_dub == datetime(2026, 1, 8) + timedelta(days=21)
          # The real-source episode 1 is untouched.
          ep1 = Episode.query.filter_by(anime_id=aid, episode_number=1).first()
          assert ep1.dub_source == "crunchyroll_rss"


  def test_seeder_falls_back_to_default_lag(app):
      with app.app_context():
          a = _airing_anime("No Dub Data Show")
          db.session.add(a)
          db.session.flush()
          db.session.add(Episode(
              anime_id=a.id, episode_number=1, air_date_sub=datetime(2026, 2, 1),
          ))
          db.session.commit()
          aid = a.id

      main([])

      with app.app_context():
          ep = Episode.query.filter_by(anime_id=aid, episode_number=1).first()
          assert ep.dub_source == SYNTHETIC_TAG
          assert ep.air_date_dub == datetime(2026, 2, 1) + timedelta(days=LAG_DAYS)
  ```
  Run `python -m pytest tests/test_seed_dub_schedule.py -v` → FAIL (`_learned_lag_days` missing).

- [ ] **Step 2: Add the helper.** In `seed_dub_schedule.py`, near the top constants:
  ```python
  def _learned_lag_days(deltas: list[int]) -> int | None:
      """Median sub->dub gap (days) from a show's real dub data points, or None."""
      from statistics import median
      return int(median(deltas)) if deltas else None
  ```

- [ ] **Step 3: Use per-show lag in the projector.** Replace the single bulk UPDATE block (the `stmt = (update(Episode).where(*eligible_clauses).values(air_date_dub=sa_func.datetime(Episode.air_date_sub, f"+{LAG_DAYS} days"), ...)` … through its `print(...)`) with:
  ```python
          # Learn each show's real sub->dub gap (sparse query — only episodes
          # that already carry a real dub date are hydrated, so this stays well
          # under the memory budget the bulk path was protecting).
          from collections import defaultdict
          real_rows = (
              db.session.query(
                  Episode.anime_id, Episode.air_date_sub, Episode.air_date_dub
              )
              .filter(
                  Episode.anime_id.in_(anime_ids),
                  Episode.air_date_sub.isnot(None),
                  Episode.air_date_dub.isnot(None),
                  preserve_clause,
              )
              .all()
          )
          gaps = defaultdict(list)
          for aid, sub, dub in real_rows:
              gaps[aid].append((dub - sub).days)
          learned = {
              aid: lag
              for aid, ds in gaps.items()
              if (lag := _learned_lag_days(ds)) is not None
          }

          n_set = 0
          # Shows with real dub data: project at their own observed lag.
          for aid, lag in learned.items():
              res = db.session.execute(
                  update(Episode)
                  .where(*eligible_clauses, Episode.anime_id == aid)
                  .values(
                      air_date_dub=sa_func.datetime(
                          Episode.air_date_sub, f"+{lag} days"
                      ),
                      dub_source=SYNTHETIC_TAG,
                  )
                  .execution_options(synchronize_session=False)
              )
              n_set += res.rowcount or 0
          # Everyone else: the flat default lag.
          default_ids = [aid for aid in anime_ids if aid not in learned]
          if default_ids:
              res = db.session.execute(
                  update(Episode)
                  .where(*eligible_clauses, Episode.anime_id.in_(default_ids))
                  .values(
                      air_date_dub=sa_func.datetime(
                          Episode.air_date_sub, f"+{LAG_DAYS} days"
                      ),
                      dub_source=SYNTHETIC_TAG,
                  )
                  .execution_options(synchronize_session=False)
              )
              n_set += res.rowcount or 0
          db.session.commit()
          print(
              f"wrote air_date_dub on {n_set} episodes "
              f"({len(learned)} shows at learned lag, rest at {LAG_DAYS}d default, "
              f"tag={SYNTHETIC_TAG!r}); preserved {preserved_count} real rows"
          )
  ```
  (Indentation: this block lives inside `with app.app_context():`. `update`, `or_`, `sa_func`, `preserve_clause`, `eligible_clauses`, `anime_ids`, `preserved_count` are already in scope from the surrounding code.)

- [ ] **Step 4: Run → pass** `python -m pytest tests/test_seed_dub_schedule.py -v`.

- [ ] **Step 5: Commit**
  ```bash
  git add seed_dub_schedule.py tests/test_seed_dub_schedule.py
  git commit -m "feat(schedule): project synthetic dub dates at each show's learned lag"
  ```

---

## Task 2: Dub-schedule runbook

**Files:** `docs/runbooks/dub-schedule.md` (new)

- [ ] **Step 1:** Create `docs/runbooks/dub-schedule.md`:
  ```markdown
  # Dub schedule runbook

  How an episode's dub air date is determined, best source first:

  1. **Crunchyroll RSS** (`sync_dub_crunchyroll.py`) — real, season-aware
     (matches the correct season's row; see season-matching PR).
  2. **AnimeSchedule.net** (`sync_dub_animeschedule.py`) — real + season-correct,
     **but its API key is currently 401-ing**. Restoring accuracy is primarily an
     ops task: set a valid `ANIMESCHEDULE_API_KEY` env var. This is the single
     biggest lever for dub-date accuracy and is outside code.
  3. **User dub reports** (`routes/dub_reports.py`) — accepted reports overwrite
     the date with `dub_source = user:<name>`.
  4. **Synthetic fallback** (`seed_dub_schedule.py`) — for episodes with no real
     dub date, projects `air_date_sub + lag`, where `lag` is the show's own
     observed sub→dub median when it has real dub data, else 56 days. Tagged
     `synthetic_lag_8w` and shown with the "estimated" badge.

  ## Running the synthetic seeder

      python seed_dub_schedule.py            # write/refresh synthetic dubs
      python seed_dub_schedule.py --dry-run  # report only

  The seeder's date math uses SQLite's `datetime(...)`, so it runs on the **Fly
  (SQLite)** deployment — manually or via a Fly scheduled machine. It does **not**
  run on Render (Postgres); there, dub data comes from the Crunchyroll /
  AnimeSchedule crons + user reports.
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add docs/runbooks/dub-schedule.md
  git commit -m "docs(runbook): document the dub-date pipeline and synthetic seeder"
  ```

---

## Task 3: Full verification

- [ ] `python -m pytest tests/test_seed_dub_schedule.py tests/test_schedule_week.py tests/test_dub_crunchyroll.py -v` then `python -m pytest -q` (all green).

---

## Self-review
- **Spec coverage:** learned per-show lag (Task 1) ✓; runbook documenting Fly execution + AnimeSchedule key (Task 2) ✓; tests for helper + integration (Task 1) ✓; no Render cron (SQLite-only, corrected) ✓.
- **No placeholders:** helper + projector rewrite + runbook given in full.
- **OOM-safety:** only sparse real-dub rows are hydrated for the medians; projections run as SQL UPDATEs (per-show + one default) — no full-cohort hydration.
- **Back-compat:** shows without real dub data still project at 56 days; tag/idempotency/preserve-real-sources unchanged.
- **Out of scope:** restoring the API key (ops), Postgres-portable date math, season/number matching (#13).
