# Schedule Freshness & Variety (Sub-project A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Episodes show on the correct local day (tz-aware bucketing), the schedule stays populated (a daily `--airing` refresh cron), and the "estimated" dub tag is honest.

**Architecture:** Backend `/api/schedule/week` buckets by the viewer's timezone; the frontend sends its IANA tz. A new `sync_anilist.py --airing` mode refreshes currently-`RELEASING` titles, scheduled daily in `render.yaml`. Tooltip copy fix.

**Tech Stack:** Flask + SQLAlchemy + `zoneinfo` (Python 3.13), pytest; React + TS + Vite; AniList GraphQL; Render cron.

Spec: `docs/superpowers/specs/2026-06-18-schedule-freshness-design.md`
Branch: `feat/schedule-freshness`

**Conventions:** mobile/back-compat — `tz` is optional (defaults to today's UTC behavior). NO AI attribution in commits. Frontend cmds from `frontend/`. Edit via desktop-commander/Grep first if native Read is truncated.

---

## Task 1: Timezone-aware day bucketing

**Files:** `routes/schedule.py`, `frontend/src/lib/api.ts`, `frontend/src/hooks/useScheduleWeek.ts`; test `tests/test_schedule_week.py`

- [ ] **Step 1: Failing backend test** — add to `tests/test_schedule_week.py` (mirror its existing fixtures/helpers; it already creates a user + anime + episodes and calls `/api/schedule/week`). Test that an episode airing at `02:30Z` buckets into the **previous** local day under a negative-offset tz:
  ```python
  def test_week_buckets_by_viewer_timezone(client, app, auth_headers):
      headers, user = auth_headers
      # Create an anime + a sub episode airing 2026-06-17 02:30 UTC.
      # (Use the file's existing helper for making an anime + episode; set
      #  air_date_sub = datetime(2026, 6, 17, 2, 30).)
      # Week anchor = Sunday 2026-06-14 (local).
      r = client.get(
          "/api/schedule/week?week=2026-06-14&lang=sub&tz=America/Toronto",
          headers=headers,
      )
      body = r.get_json()
      days = {d["date"]: d["episodes"] for d in body["days"]}
      # Toronto is UTC-4 in June: 02:30Z -> 22:30 on 2026-06-16 local.
      assert len(days["2026-06-16"]) == 1
      assert all(len(days[k]) == 0 for k in days if k != "2026-06-16")

  def test_week_invalid_tz_falls_back_to_utc(client, app, auth_headers):
      headers, user = auth_headers
      # Same episode; invalid tz -> UTC bucketing -> 2026-06-17.
      r = client.get(
          "/api/schedule/week?week=2026-06-14&lang=sub&tz=Not/AZone",
          headers=headers,
      )
      days = {d["date"]: d["episodes"] for d in r.get_json()["days"]}
      assert len(days["2026-06-17"]) == 1
  ```
  (Adapt the anime/episode creation to the file's existing helpers; if none, create via `db.session.add(Anime(...))` + `Episode(anime_id=..., episode_number=1, air_date_sub=datetime(2026,6,17,2,30))` inside `app.app_context()`.)
- [ ] **Step 2: Run → fail** `python -m pytest tests/test_schedule_week.py -k timezone -v` (Toronto test fails — currently buckets by UTC into 06-17).
- [ ] **Step 3: Implement backend.** In `routes/schedule.py`:
  - Add import at top: `from zoneinfo import ZoneInfo, ZoneInfoNotFoundError`.
  - In `schedule_week`, after parsing `mine`, resolve the viewer tz:
    ```python
    tz_name = (request.args.get("tz") or "").strip()
    try:
        view_tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        view_tz = timezone.utc
    ```
  - Widen the DB query window by ±1 day so tz-shifted edge episodes aren't dropped. Replace the `start_naive`/`end_naive` used in `_collect`'s filter with:
    ```python
    q_start_naive = (week_start - timedelta(days=1)).replace(tzinfo=None)
    q_end_naive = (week_end + timedelta(days=1)).replace(tzinfo=None)
    ```
    and use `field >= q_start_naive`, `field < q_end_naive` in `_collect`.
  - Change the bucket key to the viewer-local date:
    ```python
    bucket_key = air_at.astimezone(view_tz).date().isoformat()
    ```
    (The 7 seeded `buckets` keys stay `week_start + i days`; the `if bucket_key not in buckets: continue` guard already drops out-of-week episodes pulled in by the ±1-day margin.)
- [ ] **Step 4: Frontend sends tz.** In `frontend/src/lib/api.ts`, extend `getScheduleWeek` to accept an optional `tz` and append `&tz=`:
  ```ts
  getScheduleWeek: (week: string, lang = "both", mine = false, tz?: string) =>
    request<ScheduleWeekResponse>(
      `/schedule/week?week=${week}&lang=${lang}&mine=${mine ? 1 : 0}` +
        (tz ? `&tz=${encodeURIComponent(tz)}` : "")
    ),
  ```
  (Match the existing `getScheduleWeek` shape/return type — read it first and preserve it.) In `frontend/src/hooks/useScheduleWeek.ts`, compute the tz once and pass it, and add it to the query key:
  ```ts
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return useQuery({
    queryKey: ["schedule-week", week, lang, mine, tz],
    queryFn: () => api.getScheduleWeek(week, lang, mine, tz),
    staleTime: 60_000,
    enabled: Boolean(week),
  });
  ```
- [ ] **Step 5: Run → pass** `python -m pytest tests/test_schedule_week.py -v` (all pass) and `npm --prefix frontend run build` (clean).
- [ ] **Step 6: Commit**
  ```bash
  git add routes/schedule.py frontend/src/lib/api.ts frontend/src/hooks/useScheduleWeek.ts tests/test_schedule_week.py
  git commit -m "fix(schedule): bucket episodes by the viewer's timezone, not UTC"
  ```

---

## Task 2: `--airing` sync mode (freshness)

**Files:** `utils/anilist.py`, `sync_anilist.py`; test `tests/test_sync_anilist.py`

- [ ] **Step 1: Failing test** — append to `tests/test_sync_anilist.py` (it imports from `sync_anilist`, has the `app` fixture + `_media` helper):
  ```python
  class _AiringClient:
      """Stand-in exposing fetch_airing_page(page) like AniListClient."""

      def __init__(self, pages):
          self.pages = pages  # list of {"results": [...], "page_info": {...}}
          self.calls = []

      def fetch_airing_page(self, page=1, per_page=50):
          self.calls.append(page)
          return self.pages[page - 1] if page <= len(self.pages) else {
              "results": [], "page_info": {"has_next_page": False}
          }


  def test_run_airing_sync_upserts_releasing(app):
      from sync_anilist import run_airing_sync
      from models import Anime

      with app.app_context():
          page = {
              "results": [_media(anilist_id=70001, title="Airing Show", year=2026)],
              "page_info": {"has_next_page": False},
          }
          client = _AiringClient([page])
          summary = run_airing_sync(client, max_pages=5, dry_run=False)
          assert summary["media_processed"] == 1
          assert Anime.query.filter_by(anilist_id=70001).count() == 1
  ```
  Run `python -m pytest tests/test_sync_anilist.py -k airing -v` → FAIL (`run_airing_sync` missing).
- [ ] **Step 2: AniList query + client method.** In `utils/anilist.py`, add an `AIRING_QUERY` mirroring `CATALOG_QUERY` (it uses `...AnimeFields` + a `nextAiringEpisode { ... }` block) but replacing the `seasonYear: $seasonYear` filter with `status: RELEASING` and `sort: POPULARITY_DESC`:
  ```python
  AIRING_QUERY = """
  query ($page: Int, $perPage: Int) {
    Page(page: $page, perPage: $perPage) {
      pageInfo { hasNextPage currentPage lastPage perPage }
      media(type: ANIME, sort: POPULARITY_DESC, status: RELEASING) {
        ...AnimeFields
        nextAiringEpisode { episode airingAt timeUntilAiring }
      }
    }
  }
  """ + ANIME_FRAGMENT
  ```
  (Read the exact `CATALOG_QUERY` + `ANIME_FRAGMENT` concatenation pattern and `fetch_catalog_page` first, and mirror them precisely — same fragment variable, same `nextAiringEpisode` subfields.) Then add a `fetch_airing_page(self, page=1, per_page=50)` method on `AniListClient` mirroring `fetch_catalog_page` but calling `AIRING_QUERY` (no `seasonYear` variable) and returning the same `{"results": [...normalized...], "page_info": {...}}` shape.
- [ ] **Step 3: `run_airing_sync` + CLI.** In `sync_anilist.py`, add a `run_airing_sync(client, max_pages=None, dry_run=False)` mirroring `run_format_sync` (paginate `client.fetch_airing_page`, call `process_media_entry(media, dry_run)` per result, commit per page when not dry-run, stop at `max_pages` or when `has_next_page` is false; return a summary dict with `media_processed`/`pages_processed`). Default `max_pages` for `--airing` to a bounded value (e.g. 10 → ~500 shows). Add a `--airing` argparse flag and, in `main()`'s `try` block (alongside the `--ids` / orphan branches, before the year-sync), a branch:
  ```python
  if args.airing:
      from utils.anilist import AniListClient as _AniListClient
      summary = run_airing_sync(_AniListClient(), max_pages=args.max_pages or 10, dry_run=args.dry_run)
      print(f"--airing done: pages={summary['pages_processed']} anime={summary['media_processed']} dry_run={args.dry_run}")
      return 0
  ```
- [ ] **Step 4: Run → pass** `python -m pytest tests/test_sync_anilist.py -v` (airing test + existing pass).
- [ ] **Step 5: Commit**
  ```bash
  git add utils/anilist.py sync_anilist.py tests/test_sync_anilist.py
  git commit -m "feat(schedule): add --airing sync mode to refresh currently-releasing shows"
  ```

---

## Task 3: Daily airing cron (Render)

**Files:** `render.yaml`; `docs/runbooks/catalog-backfill.md`

- [ ] **Step 1:** Add a cron job to `render.yaml` (duplicate the `bingery-anilist-resync` block; change name/schedule/startCommand, keep `envVars` verbatim):
  ```yaml
  - type: cron
    name: bingery-anilist-airing
    env: python
    schedule: "0 6 * * *"
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python sync_anilist.py --airing"
    envVars:
      # <-- copy the SAME envVars entries as bingery-anilist-resync, verbatim
  ```
- [ ] **Step 2:** Append a note to `docs/runbooks/catalog-backfill.md` that schedule freshness relies on `--airing` (daily on Render; Fly has no cron — run `python sync_anilist.py --airing` manually or add a scheduled machine).
- [ ] **Step 3:** Validate: `python -c "import yaml; yaml.safe_load(open('render.yaml')); print('OK')"`.
- [ ] **Step 4: Commit**
  ```bash
  git add render.yaml docs/runbooks/catalog-backfill.md
  git commit -m "ci(cron): refresh currently-airing shows daily for schedule freshness"
  ```

---

## Task 4: Honest "estimated" tooltip

**Files:** `frontend/src/features/schedule/EstimatedTag.tsx`

- [ ] **Step 1:** Change the `TOOLTIP` constant to the truth:
  ```ts
  const TOOLTIP =
    "Dub date is an approximate placeholder (~8 weeks after the sub release), not a confirmed schedule.";
  ```
- [ ] **Step 2:** `npm --prefix frontend run build` → clean.
- [ ] **Step 3: Commit**
  ```bash
  git add frontend/src/features/schedule/EstimatedTag.tsx
  git commit -m "fix(schedule): make the estimated-dub tooltip state it's a placeholder"
  ```

---

## Task 5: Full verification

- [ ] `python -m pytest tests/test_schedule_week.py tests/test_schedule.py tests/test_sync_anilist.py -v` then `python -m pytest -q` (all green).
- [ ] `npm --prefix frontend run build` clean; `npm --prefix frontend run test:run` green.
- [ ] Manual smoke: open the schedule in a non-UTC tz and confirm episodes land on the right day; run `python sync_anilist.py --airing --dry-run --max-pages 1` and confirm it reports releasing shows.

---

## Self-review
- **Spec coverage:** tz bucketing (Task 1) ✓; freshness via `--airing` + daily cron (Tasks 2–3) ✓; honest copy (Task 4) ✓; Fly gap documented (Task 3) ✓; tests for bucketing + airing sync (Tasks 1–2) ✓.
- **No placeholders:** new code (tz logic, `run_airing_sync`, `AIRING_QUERY`, cron, copy) given; the "mirror `fetch_catalog_page`/`CATALOG_QUERY`/`run_format_sync`" steps name the exact existing symbols to copy and the one change to make (status filter), and say to read them first.
- **Back-compat:** `tz` optional → unchanged behavior for old clients/tests; `--airing` is additive; no schema change (schema work is sub-project B).
- **Out of scope (later):** episode-number normalization (B), season identity (C), real dub estimation (D).
