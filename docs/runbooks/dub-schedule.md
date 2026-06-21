# Dub schedule runbook

How an episode's dub air date is determined, best source first:

1. **Crunchyroll RSS** (`sync_dub_crunchyroll.py`) — real, season-aware (matches
   the correct season's `Anime` row; see the season-matching change).
2. **AnimeSchedule.net** (`sync_dub_animeschedule.py`) — real + season-correct,
   **but its API key is currently 401-ing**. Restoring accuracy is primarily an
   **ops** task: set a valid `ANIMESCHEDULE_API_KEY` env var. This is the single
   biggest lever for dub-date accuracy and is outside the application code.
3. **User dub reports** (`routes/dub_reports.py`) — an accepted report overwrites
   the date with `dub_source = user:<name>`.
4. **Synthetic fallback** (`seed_dub_schedule.py`) — for episodes with no real
   dub date, projects `air_date_sub + lag`, where `lag` is the show's own observed
   sub→dub **median** when it has at least one real dub data point, else **56
   days**. Tagged `synthetic_lag_8w` and shown with the "estimated" badge.

## Running the synthetic seeder

    python seed_dub_schedule.py            # write/refresh synthetic dubs
    python seed_dub_schedule.py --dry-run  # report counts only
    python seed_dub_schedule.py --reset    # wipe synthetic rows, then exit

The seeder's date math uses SQLite's `datetime(...)`, so it runs on the **Fly
(SQLite)** deployment — manually, or via a Fly scheduled machine. It does **not**
run on Render (Postgres); there, dub data comes from the Crunchyroll /
AnimeSchedule crons + user reports.
