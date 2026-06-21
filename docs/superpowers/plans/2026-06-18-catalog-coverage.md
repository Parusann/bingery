# Catalog Coverage (Missing Shows) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get `seasonYear: null` ONA/donghua (e.g. Lord of Mysteries, To Be Hero X) into the catalog via a targeted `--ids` backfill tool, and keep that category covered by scheduling the existing orphan-catcher.

**Architecture:** Add a `sync_ids(client, ids)` helper + `--ids` CLI flag to `sync_anilist.py` that fetches each AniList id (`client.get_anime`) and upserts it through the existing `process_media_entry` path. Schedule `sync_anilist.py --all-orphan-formats` as a weekly Render cron. Add a regression guard test and a backfill runbook.

**Tech Stack:** Python, Flask, SQLAlchemy, pytest; AniList GraphQL; Render cron (render.yaml).

Spec: `docs/superpowers/specs/2026-06-18-catalog-coverage-design.md`
Branch: `feat/catalog-coverage`

**Project rule:** commit messages contain NO AI/Claude attribution.

---

## Verified facts (from the codebase)
- `sync_anilist.py` `main()` builds the app context (`create_app()`, `ctx.push()`) at ~line 489, then branches; the orphan branch (`--all-orphan-formats`) returns early at ~line 539.
- `AniListClient.get_anime(anilist_id)` (`utils/anilist.py:431`) returns the normalized dict (`_normalize_anime`).
- `process_media_entry(media, dry_run=False)` (`sync_anilist.py:~99`) upserts the anime via `sync_anime_to_db(media)` + flushes + upserts episodes; it returns early without writing when `dry_run=True`. Callers commit.
- `ORPHAN_FORMATS = ("SPECIAL","OVA","ONA","MUSIC","TV_SHORT")` (`sync_anilist.py:316`); `CATALOG_QUERY_BY_FORMAT` (`utils/anilist.py:210`) queries `media(type: ANIME, sort: ID, format: $format)` — no `seasonYear`.
- Tests in `tests/test_sync_anilist.py` import `run_sync, process_media_entry, main`, use a `_media(anilist_id=, title=, year=)` helper to build normalized media, drive functions directly inside `app.app_context()`, and call `main([...])` for CLI-arg tests.
- `render.yaml` has a `- type: cron` job `bingery-anilist-resync` (schedule `"0 3 * * 0"`, `startCommand: python sync_anilist.py --full --since=...`) with an `envVars:` block wiring `JWT_SECRET_KEY` (fromService) + `DATABASE_URL` (fromDatabase connectionString).

---

## Task 1: `--ids` targeted backfill (tool + tests)

**Files:**
- Modify: `sync_anilist.py` (add `sync_ids()` + the `--ids` arg + the early branch in `main()`)
- Test: `tests/test_sync_anilist.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sync_anilist.py` (it already imports from `sync_anilist` and has the `app` fixture + `_media` helper):

```python
class _IdClient:
    """Stand-in for AniListClient exposing get_anime(id) from a dict."""

    def __init__(self, by_id):
        self.by_id = by_id
        self.calls = []

    def get_anime(self, anilist_id):
        self.calls.append(anilist_id)
        return self.by_id.get(anilist_id)


def test_sync_ids_backfills_specific_titles(app):
    from sync_anilist import sync_ids
    from models import Anime

    with app.app_context():
        client = _IdClient(
            {137667: _media(anilist_id=137667, title="Lord of Mysteries", year=2025)}
        )
        summary = sync_ids(client, [137667])
        assert summary["synced"] == 1
        assert summary["failed"] == 0
        assert Anime.query.filter_by(anilist_id=137667).count() == 1
        assert client.calls == [137667]

        # Idempotent: a second run updates rather than duplicating.
        summary2 = sync_ids(client, [137667])
        assert summary2["synced"] == 1
        assert Anime.query.filter_by(anilist_id=137667).count() == 1


def test_sync_ids_skips_unknown_without_crashing(app):
    from sync_anilist import sync_ids
    from models import Anime

    with app.app_context():
        client = _IdClient({})  # get_anime returns None for any id
        summary = sync_ids(client, [999999])
        assert summary["synced"] == 0
        assert summary["failed"] == 1
        assert Anime.query.filter_by(anilist_id=999999).count() == 0


def test_sync_ids_dry_run_writes_nothing(app):
    from sync_anilist import sync_ids
    from models import Anime

    with app.app_context():
        client = _IdClient(
            {7: _media(anilist_id=7, title="Dry Run Show", year=2024)}
        )
        summary = sync_ids(client, [7], dry_run=True)
        assert summary["synced"] == 1  # counted as processed
        assert Anime.query.filter_by(anilist_id=7).count() == 0  # but not persisted
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_sync_anilist.py -k sync_ids -v`
Expected: FAIL — `ImportError: cannot import name 'sync_ids'`.

- [ ] **Step 3: Implement `sync_ids`**

In `sync_anilist.py`, add this function near `process_media_entry` (module-level, after it):

```python
def sync_ids(client, ids, dry_run=False) -> dict:
    """Backfill specific AniList media IDs.

    Fetches each id via client.get_anime() and upserts it through the same
    process_media_entry path the page-sync uses. Idempotent (upsert by
    anilist_id). Returns {"requested", "synced", "failed"}. A not-found or
    failed id is logged and skipped, not fatal.
    """
    from models import db

    requested = len(ids)
    synced = 0
    failed = 0
    for anilist_id in ids:
        try:
            media = client.get_anime(anilist_id)
        except Exception as exc:  # network / API error for one id
            print(f"  id={anilist_id}: fetch failed: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        if not media:
            print(f"  id={anilist_id}: not found on AniList")
            failed += 1
            continue
        process_media_entry(media, dry_run=dry_run)
        if not dry_run:
            db.session.commit()
        title = media.get("title") or media.get("title_romaji") or anilist_id
        print(f"  id={anilist_id}: {'(dry-run) ' if dry_run else ''}synced {title}")
        synced += 1
    print(
        f"--ids done: requested={requested} synced={synced} failed={failed} "
        f"dry_run={dry_run}"
    )
    return {"requested": requested, "synced": synced, "failed": failed}
```

- [ ] **Step 4: Wire the `--ids` CLI flag in `main()`**

In `main()`'s argparse setup (alongside the other `parser.add_argument(...)` calls, NOT inside the `--full`/`--resume` mutually-exclusive group), add:

```python
    parser.add_argument(
        "--ids",
        type=int,
        nargs="+",
        metavar="ANILIST_ID",
        help=(
            "Backfill specific AniList media IDs (space-separated), e.g. "
            "--ids 137667 156092. Fetches each by id and upserts it."
        ),
    )
```

Then, inside the `try:` block right AFTER the app context is pushed and BEFORE the orphan-catcher branch (`if args.media_format or args.all_orphan_formats:`), add:

```python
        # ── Targeted backfill branch: --ids ─────────────────────────────────
        if args.ids:
            from utils.anilist import AniListClient as _AniListClient
            client = _AniListClient()
            summary = sync_ids(client, args.ids, dry_run=args.dry_run)
            return 0 if summary["failed"] < summary["requested"] else 1
```

(Returns 0 if at least one id synced; 1 only if every requested id failed.)

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_sync_anilist.py -v`
Expected: PASS (the three new `sync_ids` tests + all existing sync tests).

- [ ] **Step 6: Commit**

```bash
git add sync_anilist.py tests/test_sync_anilist.py
git commit -m "feat(sync): add --ids flag to backfill specific AniList titles"
```

---

## Task 2: Regression guard for the orphan-catcher

**Files:**
- Test: `tests/test_sync_anilist.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_sync_anilist.py`:

```python
def test_orphan_catcher_reaches_seasonyear_null_ona():
    """Guard the coverage fix: the orphan-catcher must keep covering ONA, and
    its query must NOT filter by seasonYear (that's what hides donghua like
    Lord of Mysteries / To Be Hero X)."""
    from sync_anilist import ORPHAN_FORMATS
    from utils.anilist import CATALOG_QUERY_BY_FORMAT

    assert "ONA" in ORPHAN_FORMATS
    assert "seasonYear" not in CATALOG_QUERY_BY_FORMAT
```

- [ ] **Step 2: Run to verify it passes**

Run: `python -m pytest tests/test_sync_anilist.py::test_orphan_catcher_reaches_seasonyear_null_ona -v`
Expected: PASS (the current code already satisfies this — it's a guard against future regression).

- [ ] **Step 3: Commit**

```bash
git add tests/test_sync_anilist.py
git commit -m "test(sync): guard that the orphan-catcher covers seasonYear-null ONA"
```

---

## Task 3: Schedule the orphan-catcher (Render cron)

**Files:**
- Modify: `render.yaml`

- [ ] **Step 1: Add a weekly orphan-catcher cron job**

Duplicate the existing `bingery-anilist-resync` cron job block and change exactly three things: the `name`, the `schedule`, and the `startCommand`. Keep its `env`, `buildCommand`, and the entire `envVars:` block identical (same `JWT_SECRET_KEY` fromService + `DATABASE_URL` fromDatabase wiring). The new job:

```yaml
  - type: cron
    name: bingery-anilist-orphans
    env: python
    schedule: "0 5 * * 0"
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python sync_anilist.py --all-orphan-formats"
    envVars:
      # (copy the SAME envVars entries as bingery-anilist-resync, verbatim)
```

Schedule `"0 5 * * 0"` = Sundays 05:00 UTC, 2h after the `"0 3 * * 0"` main resync so they don't overlap.

- [ ] **Step 2: Verify YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('render.yaml')); print('render.yaml OK')"`
Expected: `render.yaml OK` (if PyYAML isn't installed, skip — it's a config file; just eyeball the indentation matches the sibling cron jobs).

- [ ] **Step 3: Commit**

```bash
git add render.yaml
git commit -m "ci(cron): schedule the orphan-catcher weekly to cover seasonYear-null ONA"
```

---

## Task 4: Backfill runbook + final verification

**Files:**
- Create: `docs/runbooks/catalog-backfill.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/catalog-backfill.md`:

```markdown
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
entries. Heavier (many pages, AniList rate limits). This now also runs weekly
on Render (cron `bingery-anilist-orphans`, Sundays 05:00 UTC).

## Per deployment

- **Render** (Postgres + cron): the weekly `bingery-anilist-orphans` job keeps
  coverage current. To populate immediately, run either command above as a
  one-off job against the production database.
- **Fly** (SQLite shipped once, no cron): there is no recurring sync on Fly. To
  add titles, either run a command above against the database Fly serves and
  redeploy, or add a scheduled machine that runs the orphan-catcher. Until then
  Fly's catalog only changes when the DB is re-shipped.
```

- [ ] **Step 2: Full verification**

Run: `python -m pytest tests/test_sync_anilist.py -v` then `python -m pytest -q`
Expected: all PASS (additive change; nothing else affected).

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/catalog-backfill.md
git commit -m "docs(runbook): how to backfill missing catalog titles"
```

---

## Self-review

- **Spec coverage:** targeted `--ids` tool (Task 1) ✓; schedule orphan-catcher (Task 3) ✓; regression guard (Task 2) ✓; backfill runbook covering both deploys (Task 4) ✓; tests for `--ids` + guard (Tasks 1, 2) ✓.
- **No placeholders:** every code step has complete code; commands have expected output. The render.yaml `envVars:` is the one "copy verbatim" instruction — explicit and unavoidable (the block contains deploy-specific service refs that must match the sibling job exactly).
- **Type/name consistency:** `sync_ids(client, ids, dry_run=False)` returns `{requested, synced, failed}` — defined in Task 1, asserted by Task 1's tests; `process_media_entry`/`get_anime`/`ORPHAN_FORMATS`/`CATALOG_QUERY_BY_FORMAT` are existing names used as-is.
- **Out of scope (per spec):** live-search fallback, seasonYear-chunker rewrite, country/format filters — none added.
- **Ops note:** the named titles appear in prod only after a backfill command is actually run against the live DB (runbook Step 1) — code alone doesn't mutate prod.
