# /schedule Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `/schedule` as a week-anchored day-of-week board with a sticky 7-chip strip, an editorial banner per day, prominent watchlist treatment, and accurate browser-local times — backed by a new `/api/schedule/week` endpoint that exposes `on_watchlist` and `estimated` flags.

**Architecture:** Backend adds one new endpoint to `routes/schedule.py` (legacy `/upcoming` left intact for `NextEpisodeWidget`). Frontend deletes the existing `ScheduleCalendar`/`ScheduleEpisodeRow` and replaces them with a fresh component tree under `frontend/src/features/schedule/`, driven by URL state (`?week=&lang=&mine=`). All visuals follow the locked design handoff bundle at `Bingery/design_handoff_schedule/`.

**Tech Stack:** Flask + SQLAlchemy (Python 3.13) for the API; React 18 + TypeScript + Tailwind + TanStack Query for the UI; Vitest + Testing Library for component tests; Playwright for E2E.

**Spec:** `docs/superpowers/specs/2026-05-24-schedule-revamp-design.md`
**Design handoff:** `Bingery/design_handoff_schedule/README.md` (gitignored; not part of the repo). The handoff's `reference/schedule.css` and `reference/schedule-components.jsx` are the visual source of truth.

**Conventions in this repo (worth knowing):**
- Backend tests use the `app` and `client` fixtures from `tests/conftest.py`; DB writes use `from models import db; db.session` directly (no `db_session` fixture exists).
- Wire format is snake_case (`air_time_utc`, `on_watchlist`); TypeScript types mirror that.
- `frontend/tailwind.config.js` and `frontend/src/design/tokens.js` are generated build artifacts — edit the `.ts` siblings.
- Commit messages contain no AI attribution per user policy.

---

## File Structure

**Backend (modify in place):**
- `routes/schedule.py` — add `GET /api/schedule/week` endpoint, helpers
- `tests/test_schedule_week.py` — new test file

**Frontend (delete):**
- `frontend/src/features/schedule/ScheduleCalendar.tsx`
- `frontend/src/features/schedule/ScheduleEpisodeRow.tsx`
- `frontend/tests/features/SchedulePage.test.tsx` (rewritten)

**Frontend (new):**
- `frontend/src/features/schedule/Badge.tsx`
- `frontend/src/features/schedule/EstimatedTag.tsx`
- `frontend/src/features/schedule/EpisodeRow.tsx`
- `frontend/src/features/schedule/DayBanner.tsx`
- `frontend/src/features/schedule/DaySection.tsx`
- `frontend/src/features/schedule/DayStrip.tsx`
- `frontend/src/features/schedule/FilterPills.tsx`
- `frontend/src/features/schedule/ScheduleHeader.tsx`
- `frontend/src/features/schedule/utils.ts`
- `frontend/src/hooks/useScheduleWeek.ts`
- `frontend/tests/features/Badge.test.tsx`
- `frontend/tests/features/EstimatedTag.test.tsx`
- `frontend/tests/features/EpisodeRow.test.tsx`
- `frontend/tests/features/DayBanner.test.tsx`
- `frontend/tests/features/DaySection.test.tsx`
- `frontend/tests/features/DayStrip.test.tsx`
- `frontend/tests/features/FilterPills.test.tsx`
- `frontend/tests/features/SchedulePage.test.tsx` (rewrite of deleted)

**Frontend (modify):**
- `frontend/src/features/schedule/SchedulePage.tsx` (full rewrite, same path)
- `frontend/index.html` — add Google Fonts `<link>`
- `frontend/src/design/tokens.ts` — extend palette + fonts
- `frontend/tailwind.config.ts` — wire new tokens
- `frontend/src/types/models.ts` — add new types
- `frontend/src/types/api.ts` — add `ScheduleWeekResp`
- `frontend/src/lib/api.ts` — add `getScheduleWeek`
- `frontend/e2e/demo/06-schedule.spec.ts` — update for new layout

---

## Task 1: Backend — `/api/schedule/week` endpoint skeleton + week parsing

**Files:**
- Create: `tests/test_schedule_week.py`
- Modify: `routes/schedule.py` (add new helpers + route)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_schedule_week.py`:

```python
"""Tests for GET /api/schedule/week — week-anchored day-of-week schedule.

Uses the project conftest fixtures (`app`, `client`, `auth_headers`). DB writes
go through `db.session` directly — no `db_session` fixture in this repo.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from models import db, User, Anime, Episode, WatchlistEntry


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(email="sched@test.local", username="sched", password_hash="x")
        db.session.add(u)
        db.session.commit()
        return {"id": u.id, "email": u.email}


@pytest.fixture()
def auth_headers_for(client, user):
    res = client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "wrong"},
    )
    # We don't have a real password — login fails. Build a JWT manually instead.
    from flask_jwt_extended import create_access_token
    from app import create_app
    # Use the same app's token
    return None  # placeholder, see helper below


def _auth(app, user_id):
    """Generate a header dict carrying a valid JWT for the given user_id."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=user_id)
    return {"Authorization": f"Bearer {token}"}


def test_week_param_required(client, app, user):
    res = client.get("/api/schedule/week", headers=_auth(app, user["id"]))
    assert res.status_code == 400


def test_week_param_garbage(client, app, user):
    res = client.get(
        "/api/schedule/week?week=not-a-date",
        headers=_auth(app, user["id"]),
    )
    assert res.status_code == 400


def test_week_returns_seven_empty_days(client, app, user):
    """With no Episode rows, response is well-formed with 7 empty day buckets."""
    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["week_start"] == "2026-05-24"
    assert len(body["days"]) == 7
    expected_dates = [
        "2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27",
        "2026-05-28", "2026-05-29", "2026-05-30",
    ]
    assert [d["date"] for d in body["days"]] == expected_dates
    for d in body["days"]:
        assert d["episodes"] == []
```

- [ ] **Step 2: Run tests, confirm they fail**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: all 3 tests fail with 404 (route doesn't exist) or similar.

- [ ] **Step 3: Implement the endpoint skeleton**

Append to `routes/schedule.py`:

```python
# ─── Endpoint 3: GET /api/schedule/week ────────────────────────────────────


def _parse_week_anchor(raw: str | None) -> datetime | None:
    """Parse a ?week=YYYY-MM-DD param into a UTC midnight datetime.

    Returns None on missing/invalid input; caller is expected to 400.
    """
    if not raw:
        return None
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc)


def _iso_date(dt: datetime) -> str:
    """YYYY-MM-DD from a UTC datetime."""
    return dt.strftime("%Y-%m-%d")


@schedule_bp.route("/schedule/week", methods=["GET"])
@jwt_required()
def schedule_week():
    """Return a single week (Sunday-anchored, 7 days) of episodes.

    Query params:
        week  — ISO YYYY-MM-DD, required. Sunday of the visible week (UTC).
        lang  — "sub" | "dub" | "both", default "both".
        mine  — "0" | "1", default "0". When "1", only episodes from
                anime the requesting user has a WatchlistEntry for.
    """
    week_start = _parse_week_anchor(request.args.get("week"))
    if week_start is None:
        return jsonify({"error": "week parameter required (YYYY-MM-DD)"}), 400

    # Build 7 day-buckets (date keys) starting at week_start.
    days_payload = []
    for i in range(7):
        bucket_date = week_start + timedelta(days=i)
        days_payload.append({
            "date": _iso_date(bucket_date),
            "episodes": [],
        })

    return jsonify({
        "week_start": _iso_date(week_start),
        "days": days_payload,
    }), 200
```

- [ ] **Step 4: Run tests, confirm they pass**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add routes/schedule.py tests/test_schedule_week.py
git commit -m "feat(schedule): add /api/schedule/week endpoint skeleton with week parsing"
```

---

## Task 2: Backend — episode rows + lang filter + sort order

**Files:**
- Modify: `routes/schedule.py` (extend `schedule_week`)
- Modify: `tests/test_schedule_week.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schedule_week.py`:

```python
@pytest.fixture()
def airing_data(app, user):
    """Seed two anime, one sub episode on Sun, one dub on Wed, one sub on Wed."""
    with app.app_context():
        a1 = Anime(title="Alpha", image_url="a.jpg")
        a2 = Anime(title="Beta", image_url="b.jpg")
        db.session.add_all([a1, a2])
        db.session.flush()

        e1 = Episode(
            anime_id=a1.id,
            episode_number=1,
            air_date_sub=datetime(2026, 5, 24, 22, 30),  # Sun naive-UTC
            sub_source="anilist",
        )
        e2 = Episode(
            anime_id=a2.id,
            episode_number=4,
            air_date_dub=datetime(2026, 5, 27, 17, 0),   # Wed
            dub_source="crunchyroll_rss",
        )
        e3 = Episode(
            anime_id=a1.id,
            episode_number=2,
            air_date_sub=datetime(2026, 5, 27, 9, 0),    # Wed
            sub_source="anilist",
        )
        db.session.add_all([e1, e2, e3])
        db.session.commit()
        return {"a1_id": a1.id, "a2_id": a2.id}


def test_lang_default_is_both(client, app, user, airing_data):
    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    # Sun has 1 sub; Wed has 1 sub + 1 dub = 3 total
    total = sum(len(d["episodes"]) for d in body["days"])
    assert total == 3


def test_lang_sub_only(client, app, user, airing_data):
    res = client.get(
        "/api/schedule/week?week=2026-05-24&lang=sub",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    types = {e["type"] for d in body["days"] for e in d["episodes"]}
    assert types == {"sub"}
    assert sum(len(d["episodes"]) for d in body["days"]) == 2


def test_lang_dub_only(client, app, user, airing_data):
    res = client.get(
        "/api/schedule/week?week=2026-05-24&lang=dub",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    types = {e["type"] for d in body["days"] for e in d["episodes"]}
    assert types == {"dub"}
    assert sum(len(d["episodes"]) for d in body["days"]) == 1


def test_lang_garbage_400s(client, app, user):
    res = client.get(
        "/api/schedule/week?week=2026-05-24&lang=spanish",
        headers=_auth(app, user["id"]),
    )
    assert res.status_code == 400


def test_episodes_sorted_by_air_time_then_title(client, app, user, airing_data):
    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    wed = next(d for d in body["days"] if d["date"] == "2026-05-27")
    # 09:00 sub Alpha first, then 17:00 dub Beta
    assert [e["episode_number"] for e in wed["episodes"]] == [2, 4]


def test_episode_shape_complete(client, app, user, airing_data):
    res = client.get(
        "/api/schedule/week?week=2026-05-24&lang=sub",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    sun_ep = next(d for d in body["days"] if d["date"] == "2026-05-24")["episodes"][0]
    assert sun_ep["id"]
    assert sun_ep["anime_id"]
    assert sun_ep["anime"]["title"] == "Alpha"
    assert sun_ep["anime"]["image_url"] == "a.jpg"
    assert sun_ep["episode_number"] == 1
    assert sun_ep["air_time_utc"] == "2026-05-24T22:30:00Z"
    assert sun_ep["type"] == "sub"
    assert sun_ep["estimated"] is False
    assert sun_ep["on_watchlist"] is False
```

- [ ] **Step 2: Run tests, confirm they fail**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: 6 new tests fail; the original 3 still pass.

- [ ] **Step 3: Extend the endpoint to query and shape episodes**

Replace the `schedule_week` function body (keep the signature + docstring) with:

```python
    week_start = _parse_week_anchor(request.args.get("week"))
    if week_start is None:
        return jsonify({"error": "week parameter required (YYYY-MM-DD)"}), 400

    lang = (request.args.get("lang") or "both").lower()
    if lang not in ("sub", "dub", "both"):
        return jsonify({"error": "lang must be one of sub/dub/both"}), 400

    week_end = week_start + timedelta(days=7)
    start_naive = week_start.replace(tzinfo=None)
    end_naive = week_end.replace(tzinfo=None)

    # Bucket builder seeded with empty days so the response is always 7 long.
    buckets: dict[str, list[dict]] = {}
    for i in range(7):
        bucket_date = week_start + timedelta(days=i)
        buckets[_iso_date(bucket_date)] = []

    def _collect(field, kind: str) -> None:
        rows = (
            maybe_exclude_nsfw(
                db.session.query(Episode, Anime)
                .join(Anime, Anime.id == Episode.anime_id)
                .filter(field >= start_naive)
                .filter(field < end_naive)
            )
            .all()
        )
        for episode, anime in rows:
            raw = getattr(episode, field.key)
            air_at = _episode_air_date(raw)
            if air_at is None:
                continue
            bucket_key = _iso_date(air_at)
            if bucket_key not in buckets:
                continue
            buckets[bucket_key].append({
                "id": episode.id,
                "anime_id": anime.id,
                "anime": anime.to_dict(),
                "episode_number": episode.episode_number,
                "air_time_utc": _as_iso_z(air_at),
                "type": kind,
                "estimated": False,           # filled in Task 4
                "on_watchlist": False,        # filled in Task 3
                "_sort_air": air_at,
                "_sort_title": (anime.title or "").lower(),
            })

    if lang in ("sub", "both"):
        _collect(Episode.air_date_sub, "sub")
    if lang in ("dub", "both"):
        _collect(Episode.air_date_dub, "dub")

    days_payload = []
    for i in range(7):
        date_key = _iso_date(week_start + timedelta(days=i))
        episodes = buckets[date_key]
        episodes.sort(key=lambda e: (e["_sort_air"], e["_sort_title"]))
        for e in episodes:
            e.pop("_sort_air", None)
            e.pop("_sort_title", None)
        days_payload.append({"date": date_key, "episodes": episodes})

    return jsonify({
        "week_start": _iso_date(week_start),
        "days": days_payload,
    }), 200
```

- [ ] **Step 4: Run tests, confirm they pass**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```
git add routes/schedule.py tests/test_schedule_week.py
git commit -m "feat(schedule): /week returns episode rows with lang filter and sort"
```

---

## Task 3: Backend — `on_watchlist` flag + `mine` filter

**Files:**
- Modify: `routes/schedule.py`
- Modify: `tests/test_schedule_week.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schedule_week.py`:

```python
@pytest.fixture()
def watchlisted(app, user, airing_data):
    """Add a WatchlistEntry so the user follows Anime A."""
    with app.app_context():
        we = WatchlistEntry(
            user_id=user["id"],
            anime_id=airing_data["a1_id"],
            status="watching",
        )
        db.session.add(we)
        db.session.commit()
    return airing_data


def test_on_watchlist_flag_populated(client, app, user, watchlisted):
    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    all_eps = [e for d in body["days"] for e in d["episodes"]]
    by_anime = {e["anime_id"]: e["on_watchlist"] for e in all_eps}
    assert by_anime[watchlisted["a1_id"]] is True
    assert by_anime[watchlisted["a2_id"]] is False


def test_mine_filter_only_returns_watchlisted(client, app, user, watchlisted):
    res = client.get(
        "/api/schedule/week?week=2026-05-24&mine=1",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    all_eps = [e for d in body["days"] for e in d["episodes"]]
    assert all(e["on_watchlist"] for e in all_eps)
    anime_ids = {e["anime_id"] for e in all_eps}
    assert anime_ids == {watchlisted["a1_id"]}


def test_mine_zero_returns_all(client, app, user, watchlisted):
    res = client.get(
        "/api/schedule/week?week=2026-05-24&mine=0",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    anime_ids = {e["anime_id"] for d in body["days"] for e in d["episodes"]}
    assert anime_ids == {watchlisted["a1_id"], watchlisted["a2_id"]}
```

- [ ] **Step 2: Run tests, confirm they fail**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: 3 new tests fail.

- [ ] **Step 3: Wire watchlist join**

In `routes/schedule.py`, add a helper near the top (after imports) and update `schedule_week`:

```python
from flask_jwt_extended import get_jwt_identity  # add to existing import line

def _watchlisted_anime_ids(user_id: int) -> set[int]:
    """Return the set of anime IDs the user has any WatchlistEntry for."""
    from models import WatchlistEntry
    rows = db.session.query(WatchlistEntry.anime_id).filter_by(user_id=user_id).all()
    return {r[0] for r in rows}
```

Inside `schedule_week`, after the `lang` validation, add:

```python
    mine_raw = (request.args.get("mine") or "0").strip()
    mine = mine_raw == "1"

    user_id = get_jwt_identity()
    watchlist_ids = _watchlisted_anime_ids(user_id)
```

Then inside the `_collect` loop, replace `"on_watchlist": False,` with:

```python
                "on_watchlist": anime.id in watchlist_ids,
```

And immediately after the loop appends a row, if `mine` is True and `anime.id not in watchlist_ids`, skip. The cleanest expression: inside `_collect`, before the append:

```python
            if mine and anime.id not in watchlist_ids:
                continue
```

- [ ] **Step 4: Run tests, confirm they pass**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: all 12 tests pass.

- [ ] **Step 5: Commit**

```
git add routes/schedule.py tests/test_schedule_week.py
git commit -m "feat(schedule): /week supports mine filter and on_watchlist flag"
```

---

## Task 4: Backend — `estimated` flag + NSFW carryover

**Files:**
- Modify: `routes/schedule.py`
- Modify: `tests/test_schedule_week.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schedule_week.py`:

```python
def test_estimated_flag_true_for_synthetic_dub(client, app, user):
    with app.app_context():
        a = Anime(title="EstShow", image_url="e.jpg")
        db.session.add(a)
        db.session.flush()
        e = Episode(
            anime_id=a.id,
            episode_number=1,
            air_date_dub=datetime(2026, 5, 25, 12, 0),
            dub_source="synthetic_lag_8w",
        )
        db.session.add(e)
        db.session.commit()
        anime_id = a.id

    res = client.get(
        "/api/schedule/week?week=2026-05-24&lang=dub",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    dub_eps = [e for d in body["days"] for e in d["episodes"]]
    target = next(e for e in dub_eps if e["anime_id"] == anime_id)
    assert target["estimated"] is True


def test_estimated_flag_false_for_real_dub_and_subs(client, app, user, airing_data):
    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    all_eps = [e for d in body["days"] for e in d["episodes"]]
    assert all(e["estimated"] is False for e in all_eps)


def test_nsfw_hentai_excluded(client, app, user):
    with app.app_context():
        # NsfwShow has genre "Hentai" → excluded unconditionally.
        a = Anime(title="NsfwShow", image_url="n.jpg", genres="Hentai,Action")
        db.session.add(a)
        db.session.flush()
        e = Episode(
            anime_id=a.id,
            episode_number=1,
            air_date_sub=datetime(2026, 5, 25, 10, 0),
            sub_source="anilist",
        )
        db.session.add(e)
        db.session.commit()

    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    titles = {e["anime"]["title"] for d in body["days"] for e in d["episodes"]}
    assert "NsfwShow" not in titles
```

- [ ] **Step 2: Run tests, confirm they fail**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: 2 of the 3 new tests fail (`estimated_flag_true_for_synthetic_dub`, possibly `nsfw` if not yet wired). The "false" test should already pass because the field defaults to False.

- [ ] **Step 3: Compute `estimated` from `dub_source`**

In `routes/schedule.py`, in `_collect`, replace `"estimated": False,` with:

```python
                "estimated": (kind == "dub" and (episode.dub_source or "") == "synthetic_lag_8w"),
```

NSFW filtering is already applied via `maybe_exclude_nsfw` from Task 2's code — no extra change needed unless the test fails. If it fails, verify the import:

```python
from utils.nsfw import maybe_exclude_nsfw  # already present at top of routes/schedule.py
```

- [ ] **Step 4: Run tests, confirm they pass**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest tests/test_schedule_week.py -v
```

Expected: all 15 tests pass.

- [ ] **Step 5: Commit**

```
git add routes/schedule.py tests/test_schedule_week.py
git commit -m "feat(schedule): /week marks synthetic dub dates as estimated"
```

---

## Task 5: Frontend foundation — Google Fonts + tokens

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/design/tokens.ts`

- [ ] **Step 1: Add Google Fonts link**

In `frontend/index.html`, before `</head>`, insert:

```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      rel="stylesheet"
      href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600&family=Geist+Mono:wght@400;500&family=Instrument+Serif:ital@0;1&display=swap"
    />
```

- [ ] **Step 2: Extend tokens.ts with new palette and fonts**

Read `frontend/src/design/tokens.ts` to see the current shape. Inside the existing `palette` object literal (do not remove anything), insert the new keys below — placement doesn't matter as long as they're inside `palette = { ... }`:

```ts
// Schedule revamp tokens (2026-05-24)
peach: "#f4b690",
peachHi: "#ffd0ad",
peachDeep: "#d99368",
sage: "#9BB8A8",
sageBg: "rgba(155,184,168,0.10)",
sageBd: "rgba(155,184,168,0.38)",
gold: "#f4cf90",
goldBd: "rgba(244,207,144,0.42)",
goldGlow: "rgba(244,207,144,0.18)",
ink: "#f3ece4",
ink2: "#cbc1b6",
mute: "#8a8090",
mute2: "#5a5263",
line: "rgba(243,236,228,0.08)",
line2: "rgba(243,236,228,0.14)",
rowBg: "rgba(255,255,255,0.025)",
rowBgHover: "rgba(255,255,255,0.05)",
rowBd: "rgba(255,255,255,0.06)",
```

Update the `font` export to include the new families (keeping the existing ones available):

```ts
export const font = {
  display: "Instrument Serif",
  body: "Geist",
  mono: "Geist Mono",
};
```

If the original `font` already had values like `Inter` or `JetBrains Mono`, the change is a swap. Existing pages will pick up Geist/Instrument Serif automatically — confirm by skimming any page that uses `font-display`/`font-mono`. If any look broken visually, that's flagged as a follow-up; the scope of this plan is `/schedule`.

- [ ] **Step 3: Commit**

```
git add frontend/index.html frontend/src/design/tokens.ts
git commit -m "feat(frontend): add Instrument Serif / Geist / Geist Mono and schedule palette"
```

---

## Task 6: Frontend foundation — Tailwind config exposes new tokens

**Files:**
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Add new color entries to the Tailwind theme**

In `frontend/tailwind.config.ts`, extend the `colors` block:

```ts
peach: palette.peach,
"peach-hi": palette.peachHi,
"peach-deep": palette.peachDeep,
sage: palette.sage,
"sage-bg": palette.sageBg,
"sage-bd": palette.sageBd,
gold: palette.gold,
"gold-bd": palette.goldBd,
"gold-glow": palette.goldGlow,
ink: palette.ink,
"ink-2": palette.ink2,
mute: palette.mute,
"mute-2": palette.mute2,
line: palette.line,
"line-2": palette.line2,
"row-bg": palette.rowBg,
"row-bg-hover": palette.rowBgHover,
"row-bd": palette.rowBd,
```

- [ ] **Step 2: Verify tsc still compiles**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/tsc -b
```

Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/tailwind.config.ts
git commit -m "feat(frontend): expose schedule palette via Tailwind utilities"
```

---

## Task 7: Frontend foundation — TypeScript types

**Files:**
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add ScheduleWeek types to models.ts**

Append to `frontend/src/types/models.ts`:

```ts
// /api/schedule/week response (revamp 2026-05-24)

export interface ScheduleWeekEpisode {
  id: number;
  anime_id: number;
  anime: AnimeSummary;
  episode_number: number;
  air_time_utc: string;       // ISO with Z
  type: "sub" | "dub";
  estimated: boolean;
  on_watchlist: boolean;
}

export interface ScheduleWeekDay {
  date: string;                // YYYY-MM-DD, UTC-keyed
  episodes: ScheduleWeekEpisode[];
}

export interface ScheduleWeekResponse {
  week_start: string;          // YYYY-MM-DD
  days: ScheduleWeekDay[];     // length 7, Sun..Sat
}
```

- [ ] **Step 2: Re-export from api.ts**

Append to `frontend/src/types/api.ts`:

```ts
import type { ScheduleWeekResponse } from "./models";
export interface ScheduleWeekResp extends ScheduleWeekResponse {}
```

- [ ] **Step 3: Verify tsc**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/tsc -b
```

Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/types/models.ts frontend/src/types/api.ts
git commit -m "feat(frontend): add ScheduleWeek* types for /api/schedule/week"
```

---

## Task 8: Frontend foundation — api client + useScheduleWeek hook

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useScheduleWeek.ts`

- [ ] **Step 1: Add the API call**

In `frontend/src/lib/api.ts`, find the existing `getSchedule` function and add below it:

```ts
async getScheduleWeek(
  week: string,
  lang: "sub" | "dub" | "both" = "both",
  mine = false,
): Promise<ScheduleWeekResp> {
  const params = new URLSearchParams({
    week,
    lang,
    mine: mine ? "1" : "0",
  });
  return this.get<ScheduleWeekResp>(`/schedule/week?${params}`);
},
```

Make sure `ScheduleWeekResp` is imported at the top of `api.ts`:

```ts
import type { ..., ScheduleWeekResp } from "@/types/api";
```

- [ ] **Step 2: Create the hook**

Create `frontend/src/hooks/useScheduleWeek.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useScheduleWeek(
  week: string,
  lang: "sub" | "dub" | "both" = "both",
  mine = false,
) {
  return useQuery({
    queryKey: ["schedule-week", week, lang, mine],
    queryFn: () => api.getScheduleWeek(week, lang, mine),
    staleTime: 60_000,
    enabled: Boolean(week),
  });
}
```

- [ ] **Step 3: Verify tsc**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/tsc -b
```

Expected: no errors.

- [ ] **Step 4: Commit**

```
git add frontend/src/lib/api.ts frontend/src/hooks/useScheduleWeek.ts
git commit -m "feat(frontend): add useScheduleWeek hook and api.getScheduleWeek"
```

---

## Task 9: Frontend — utils (week math + time formatting)

**Files:**
- Create: `frontend/src/features/schedule/utils.ts`
- Create: `frontend/tests/features/scheduleUtils.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/tests/features/scheduleUtils.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import {
  getSundayOfWeek,
  shiftWeek,
  formatLocalTime,
  formatLocalTzAbbr,
  isToday,
  todayIsoDate,
} from "@/features/schedule/utils";

describe("getSundayOfWeek", () => {
  it("returns the same date when given a Sunday", () => {
    expect(getSundayOfWeek(new Date("2026-05-24T12:00:00Z"))).toBe("2026-05-24");
  });
  it("returns the prior Sunday when given a Wednesday", () => {
    expect(getSundayOfWeek(new Date("2026-05-27T12:00:00Z"))).toBe("2026-05-24");
  });
});

describe("shiftWeek", () => {
  it("adds 7 days for +1", () => {
    expect(shiftWeek("2026-05-24", 1)).toBe("2026-05-31");
  });
  it("subtracts 7 days for -1", () => {
    expect(shiftWeek("2026-05-24", -1)).toBe("2026-05-17");
  });
  it("crosses a month boundary", () => {
    expect(shiftWeek("2026-05-31", 1)).toBe("2026-06-07");
  });
});

describe("isToday", () => {
  it("returns true for today", () => {
    expect(isToday(todayIsoDate())).toBe(true);
  });
  it("returns false for a different day", () => {
    expect(isToday("1999-01-01")).toBe(false);
  });
});

describe("formatLocalTime", () => {
  it("returns h:mm AM/PM in the user's locale", () => {
    const s = formatLocalTime("2026-05-24T22:30:00Z");
    expect(s).toMatch(/\d{1,2}:\d{2}/);
  });
});

describe("formatLocalTzAbbr", () => {
  it("returns a non-empty string", () => {
    expect(formatLocalTzAbbr().length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run tests, confirm they fail**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run scheduleUtils
```

Expected: all 8 tests fail (module not found).

- [ ] **Step 3: Implement the utils**

Create `frontend/src/features/schedule/utils.ts`:

```ts
/**
 * Helpers for the /schedule revamp.
 *
 * Week math is UTC-anchored to match the backend bucket keys; presentation
 * helpers use the user's browser timezone.
 */

export function todayIsoDate(): string {
  return toIsoDate(new Date());
}

export function toIsoDate(d: Date): string {
  // Locale-stable UTC YYYY-MM-DD.
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function getSundayOfWeek(d: Date): string {
  const utc = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dow = utc.getUTCDay(); // 0 = Sunday
  utc.setUTCDate(utc.getUTCDate() - dow);
  return toIsoDate(utc);
}

export function shiftWeek(weekStartIso: string, weeks: number): string {
  const [y, m, d] = weekStartIso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + weeks * 7);
  return toIsoDate(dt);
}

export function isToday(dateIso: string): boolean {
  return dateIso === todayIsoDate();
}

export function formatLocalTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatLocalTzAbbr(): string {
  // Best-effort short TZ name via Intl. Fallback to GMT offset.
  try {
    const parts = new Intl.DateTimeFormat(undefined, {
      timeZoneName: "short",
    }).formatToParts(new Date());
    const tz = parts.find((p) => p.type === "timeZoneName")?.value;
    if (tz) return tz;
  } catch (_) {
    /* fall through */
  }
  const offset = -new Date().getTimezoneOffset() / 60;
  return `GMT${offset >= 0 ? "+" : ""}${offset}`;
}

export function formatWeekdayLong(dateIso: string): string {
  const [y, m, d] = dateIso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function formatWeekdayShort(dateIso: string): string {
  const [y, m, d] = dateIso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.toLocaleDateString(undefined, {
    weekday: "short",
    timeZone: "UTC",
  }).toUpperCase();
}

export function dayNumber(dateIso: string): number {
  return Number(dateIso.split("-")[2]);
}
```

- [ ] **Step 4: Run tests, confirm they pass**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run scheduleUtils
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/utils.ts frontend/tests/features/scheduleUtils.test.ts
git commit -m "feat(schedule): week-math and time-formatting helpers with tests"
```

---

## Task 10: Frontend — Badge component

**Files:**
- Create: `frontend/src/features/schedule/Badge.tsx`
- Create: `frontend/tests/features/Badge.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/Badge.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "@/features/schedule/Badge";

describe("Badge", () => {
  it("renders SUB label and peach text class for sub", () => {
    render(<Badge type="sub" />);
    const el = screen.getByText("SUB");
    expect(el).toBeInTheDocument();
    expect(el.className).toMatch(/text-peach/);
  });

  it("renders DUB label and sage text class for dub", () => {
    render(<Badge type="dub" />);
    const el = screen.getByText("DUB");
    expect(el).toBeInTheDocument();
    expect(el.className).toMatch(/text-sage/);
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run Badge
```

Expected: 2 tests fail (module not found).

- [ ] **Step 3: Implement Badge**

Create `frontend/src/features/schedule/Badge.tsx`:

```tsx
export type BadgeType = "sub" | "dub";

export function Badge({ type, size = "md" }: { type: BadgeType; size?: "sm" | "md" }) {
  const label = type.toUpperCase();
  const isSub = type === "sub";
  const color = isSub ? "text-peach" : "text-sage";
  const bg = isSub ? "bg-peach/10" : "bg-sage/10";
  const border = isSub ? "border-peach/40" : "border-sage/40";
  const dotColor = isSub ? "bg-peach" : "bg-sage";
  const text = size === "sm" ? "text-[9.5px]" : "text-[11px]";
  return (
    <span
      className={`${color} ${bg} ${border} ${text} font-mono uppercase tracking-[0.18em] inline-flex items-center gap-[5px] rounded px-[9px] py-[4px] border`}
    >
      <span className={`${dotColor} h-[5px] w-[5px] rounded-full shadow-[0_0_5px_currentColor]`} />
      {label}
    </span>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run Badge
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/Badge.tsx frontend/tests/features/Badge.test.tsx
git commit -m "feat(schedule): Badge component for sub/dub variants"
```

---

## Task 11: Frontend — EstimatedTag component

**Files:**
- Create: `frontend/src/features/schedule/EstimatedTag.tsx`
- Create: `frontend/tests/features/EstimatedTag.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/EstimatedTag.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EstimatedTag } from "@/features/schedule/EstimatedTag";

describe("EstimatedTag", () => {
  it("renders 'estimated' label", () => {
    render(<EstimatedTag />);
    expect(screen.getByText(/estimated/i)).toBeInTheDocument();
  });

  it("exposes the tooltip text via title attribute", () => {
    render(<EstimatedTag />);
    const el = screen.getByText(/estimated/i).closest("span");
    expect(el?.getAttribute("title") ?? "").toMatch(/estimated/i);
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run EstimatedTag
```

Expected: fail.

- [ ] **Step 3: Implement**

Create `frontend/src/features/schedule/EstimatedTag.tsx`:

```tsx
import { Info } from "lucide-react";

const TOOLTIP =
  "Dub date is estimated based on previous release cadence.";

export function EstimatedTag() {
  return (
    <span
      title={TOOLTIP}
      className="inline-flex items-center gap-[3px] rounded-full border border-dashed border-line-2 px-[7px] py-[2px] text-[9.5px] font-mono uppercase tracking-[0.1em] text-mute cursor-help"
    >
      <Info className="h-3 w-3" />
      estimated
    </span>
  );
}
```

If `lucide-react` is not already installed, install it:

```
cd C:/Users/parus/Downloads/bingery-update/frontend && npm install lucide-react
```

(Check first: `grep lucide package.json` — if present, skip the install.)

- [ ] **Step 4: Run the test, confirm it passes**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run EstimatedTag
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/EstimatedTag.tsx frontend/tests/features/EstimatedTag.test.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(schedule): EstimatedTag for synthetic dub dates"
```

---

## Task 12: Frontend — EpisodeRow component

**Files:**
- Create: `frontend/src/features/schedule/EpisodeRow.tsx`
- Create: `frontend/tests/features/EpisodeRow.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/EpisodeRow.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EpisodeRow } from "@/features/schedule/EpisodeRow";
import type { ScheduleWeekEpisode } from "@/types/models";

const base: ScheduleWeekEpisode = {
  id: 1,
  anime_id: 99,
  anime: {
    id: 99,
    title: "TestShow",
    title_english: null,
    image_url: "x.jpg",
    popularity: null,
    nsfw_level: null,
  } as any,
  episode_number: 7,
  air_time_utc: "2026-05-24T22:30:00Z",
  type: "sub",
  estimated: false,
  on_watchlist: false,
};

function renderRow(ep: ScheduleWeekEpisode) {
  return render(
    <MemoryRouter>
      <EpisodeRow episode={ep} />
    </MemoryRouter>,
  );
}

describe("EpisodeRow", () => {
  it("renders the episode title, EP number, and badge", () => {
    renderRow(base);
    expect(screen.getByText("TestShow")).toBeInTheDocument();
    expect(screen.getByText("EP 7")).toBeInTheDocument();
    expect(screen.getByText("SUB")).toBeInTheDocument();
  });

  it("renders the EstimatedTag only when estimated=true", () => {
    const { rerender } = renderRow(base);
    expect(screen.queryByText(/estimated/i)).toBeNull();
    rerender(
      <MemoryRouter>
        <EpisodeRow episode={{ ...base, type: "dub", estimated: true }} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/estimated/i)).toBeInTheDocument();
  });

  it("applies highlighted styling when on_watchlist=true", () => {
    renderRow({ ...base, on_watchlist: true });
    const link = screen.getByRole("link");
    expect(link.className).toMatch(/border-gold/);
  });

  it("links to /anime/{anime_id}", () => {
    renderRow(base);
    expect(screen.getByRole("link").getAttribute("href")).toBe("/anime/99");
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run EpisodeRow
```

Expected: fail.

- [ ] **Step 3: Implement**

Create `frontend/src/features/schedule/EpisodeRow.tsx`:

```tsx
import { Link } from "react-router-dom";
import { Clock, Star, ChevronRight } from "lucide-react";
import type { ScheduleWeekEpisode } from "@/types/models";
import { Badge } from "./Badge";
import { EstimatedTag } from "./EstimatedTag";
import { formatLocalTime, formatLocalTzAbbr } from "./utils";

export function EpisodeRow({ episode }: { episode: ScheduleWeekEpisode }) {
  const highlighted = episode.on_watchlist;
  const title = episode.anime.title_english ?? episode.anime.title;

  const containerCls = [
    "grid grid-cols-[60px_1fr_auto] gap-[18px] items-center",
    "px-4 py-[10px] rounded-lg border transition-colors group",
    highlighted
      ? "bg-gold/[0.025] border-gold/20 hover:bg-gold/[0.055] hover:border-gold/[0.34]"
      : "bg-row-bg border-row-bd hover:bg-row-bg-hover hover:border-line-2",
  ].join(" ");

  const titleCls = [
    "font-display text-[21px] leading-tight tracking-tight line-clamp-1",
    highlighted ? "bg-gradient-to-b from-ink to-gold bg-clip-text text-transparent" : "text-ink",
  ].join(" ");

  return (
    <Link to={`/anime/${episode.anime_id}`} className={containerCls}>
      <div className="relative">
        {episode.anime.image_url ? (
          <img
            src={episode.anime.image_url}
            alt=""
            className="h-[80px] w-[60px] rounded-lg object-cover shadow-md"
          />
        ) : (
          <div className="h-[80px] w-[60px] rounded-lg bg-white/5" />
        )}
        {highlighted && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-gold text-[10px] text-bg">
            <Star className="h-2.5 w-2.5" fill="currentColor" />
          </span>
        )}
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={titleCls}>{title}</span>
          <span className="font-mono text-[10px] tracking-[0.14em] text-ink-2 rounded px-[6px] py-[2px] bg-white/5">
            EP {episode.episode_number}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-[12px] text-ink-2">
          <Clock className="h-3 w-3" />
          <span>{formatLocalTime(episode.air_time_utc)}</span>
          <span className="font-mono text-[10px] tracking-[0.08em] rounded px-[5px] py-[1px] bg-white/5 text-mute">
            {formatLocalTzAbbr()}
          </span>
          {episode.estimated && <EstimatedTag />}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Badge type={episode.type} />
        <ChevronRight className="h-4 w-4 text-mute transition-transform group-hover:translate-x-[2px] group-hover:text-ink" />
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run EpisodeRow
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/EpisodeRow.tsx frontend/tests/features/EpisodeRow.test.tsx
git commit -m "feat(schedule): EpisodeRow with watchlist + estimated variants"
```

---

## Task 13: Frontend — DayBanner component

**Files:**
- Create: `frontend/src/features/schedule/DayBanner.tsx`
- Create: `frontend/tests/features/DayBanner.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/DayBanner.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DayBanner } from "@/features/schedule/DayBanner";
import type { ScheduleWeekEpisode } from "@/types/models";

const ep = (id: number, img: string, on_watchlist = false): ScheduleWeekEpisode => ({
  id,
  anime_id: id,
  anime: { id, title: `T${id}`, title_english: null, image_url: img, popularity: null, nsfw_level: null } as any,
  episode_number: 1,
  air_time_utc: "2026-05-24T22:30:00Z",
  type: "sub",
  estimated: false,
  on_watchlist,
});

describe("DayBanner", () => {
  it("shows weekday name and date", () => {
    render(<DayBanner date="2026-05-24" episodes={[ep(1, "a.jpg")]} isToday={false} />);
    expect(screen.getByText(/Sunday/i)).toBeInTheDocument();
    expect(screen.getByText(/May/i)).toBeInTheDocument();
  });

  it("renders TODAY pill when isToday is true", () => {
    render(<DayBanner date="2026-05-24" episodes={[ep(1, "a.jpg")]} isToday={true} />);
    expect(screen.getByText("TODAY")).toBeInTheDocument();
  });

  it("shows the episode count", () => {
    render(
      <DayBanner
        date="2026-05-24"
        episodes={[ep(1, "a.jpg"), ep(2, "b.jpg"), ep(3, "c.jpg")]}
        isToday={false}
      />,
    );
    expect(screen.getByText(/3/)).toBeInTheDocument();
    expect(screen.getByText(/episodes?/i)).toBeInTheDocument();
  });

  it("shows watchlist count when any episodes are on watchlist", () => {
    render(
      <DayBanner
        date="2026-05-24"
        episodes={[ep(1, "a.jpg", true), ep(2, "b.jpg", true), ep(3, "c.jpg", false)]}
        isToday={false}
      />,
    );
    expect(screen.getByText(/2 on your watchlist/i)).toBeInTheDocument();
  });

  it("renders an empty-banner variant when episodes is empty", () => {
    render(<DayBanner date="2026-05-24" episodes={[]} isToday={false} />);
    expect(screen.getByText(/No releases/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run DayBanner
```

Expected: fail.

- [ ] **Step 3: Implement**

Create `frontend/src/features/schedule/DayBanner.tsx`:

```tsx
import type { ScheduleWeekEpisode } from "@/types/models";
import { formatWeekdayLong } from "./utils";

export function DayBanner({
  date,
  episodes,
  isToday,
}: {
  date: string;
  episodes: ScheduleWeekEpisode[];
  isToday: boolean;
}) {
  const isEmpty = episodes.length === 0;
  const watchlistCount = episodes.filter((e) => e.on_watchlist).length;
  const collage = episodes.slice(0, 3);
  const fullLabel = formatWeekdayLong(date);

  const wrapperCls = [
    "relative overflow-hidden rounded-[22px] border",
    isEmpty ? "h-[168px]" : "h-[232px]",
    isToday
      ? "border-peach/30 shadow-[0_30px_70px_-28px_rgba(244,182,144,0.25)]"
      : "border-line-2 shadow-[0_30px_70px_-32px_rgba(0,0,0,0.6)]",
    "bg-bg-elevated",
  ].join(" ");

  return (
    <section className={wrapperCls} aria-label={`Day banner ${date}`}>
      {!isEmpty && (
        <div className="absolute inset-0 grid grid-cols-3" aria-hidden>
          {collage.map((e, i) => (
            <div
              key={e.id}
              className="bg-cover bg-center"
              style={{
                backgroundImage: e.anime.image_url ? `url(${e.anime.image_url})` : undefined,
                filter: "saturate(1.05) brightness(0.85)",
                maskImage: maskFor(i, collage.length),
                WebkitMaskImage: maskFor(i, collage.length),
              }}
            />
          ))}
        </div>
      )}

      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(10,7,16,0.20) 0%, rgba(10,7,16,0.65) 60%, rgba(10,7,16,0.92) 100%), linear-gradient(90deg, rgba(10,7,16,0.85) 0%, rgba(10,7,16,0.30) 45%, rgba(10,7,16,0.55) 100%)",
        }}
      />

      <div className="relative flex h-full flex-col justify-between p-7">
        <div className="flex items-center gap-3">
          {isToday && (
            <span className="inline-flex items-center gap-2 rounded-full bg-peach/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-peach">
              <span className="h-1.5 w-1.5 rounded-full bg-peach animate-pulse" />
              TODAY
            </span>
          )}
          <h2 className="font-display italic text-[52px] leading-none tracking-tight bg-gradient-to-b from-ink to-mute bg-clip-text text-transparent">
            {fullLabel}
          </h2>
        </div>

        {isEmpty ? (
          <p className="font-display italic text-[32px] text-ink-2">No releases</p>
        ) : (
          <div className="flex items-end justify-between">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[40px] text-peach">{episodes.length}</span>
              <span className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-mute">
                {episodes.length === 1 ? "episode" : "episodes"}
              </span>
            </div>
            {watchlistCount > 0 && (
              <span className="inline-flex items-center gap-2 rounded-full bg-gold/[0.08] border border-gold/[0.35] px-3 py-1 text-[11px] font-mono uppercase tracking-[0.18em] text-gold">
                ★ {watchlistCount} on your watchlist
              </span>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function maskFor(idx: number, total: number): string {
  if (total === 1) return "linear-gradient(90deg, #000 0%, #000 100%)";
  if (total === 2) {
    return idx === 0
      ? "linear-gradient(90deg, #000 70%, transparent 100%)"
      : "linear-gradient(90deg, transparent 0%, #000 30%)";
  }
  // 3+
  if (idx === 0) return "linear-gradient(90deg, #000 65%, transparent 100%)";
  if (idx === 1) return "linear-gradient(90deg, transparent 0%, #000 18%, #000 82%, transparent 100%)";
  return "linear-gradient(90deg, transparent 0%, #000 35%)";
}
```

- [ ] **Step 4: Run the test, confirm it passes**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run DayBanner
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/DayBanner.tsx frontend/tests/features/DayBanner.test.tsx
git commit -m "feat(schedule): DayBanner with collage, empty, and today variants"
```

---

## Task 14: Frontend — DaySection component

**Files:**
- Create: `frontend/src/features/schedule/DaySection.tsx`
- Create: `frontend/tests/features/DaySection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/DaySection.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DaySection } from "@/features/schedule/DaySection";
import type { ScheduleWeekEpisode } from "@/types/models";

const ep = (id: number, on_watchlist: boolean): ScheduleWeekEpisode => ({
  id,
  anime_id: id,
  anime: { id, title: `T${id}`, title_english: null, image_url: "x.jpg", popularity: null, nsfw_level: null } as any,
  episode_number: id,
  air_time_utc: "2026-05-24T20:00:00Z",
  type: "sub",
  estimated: false,
  on_watchlist,
});

describe("DaySection", () => {
  it("renders the banner and both episode groups", () => {
    render(
      <MemoryRouter>
        <DaySection
          date="2026-05-24"
          episodes={[ep(1, true), ep(2, false), ep(3, true)]}
          isToday={false}
          myShowsOnly={false}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.getByText("T2")).toBeInTheDocument();
    expect(screen.getByText("T3")).toBeInTheDocument();
  });

  it("only renders watchlist episodes when myShowsOnly is true", () => {
    render(
      <MemoryRouter>
        <DaySection
          date="2026-05-24"
          episodes={[ep(1, true), ep(2, false)]}
          isToday={false}
          myShowsOnly={true}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("T1")).toBeInTheDocument();
    expect(screen.queryByText("T2")).toBeNull();
  });

  it("has a section id of day-<date> for smooth-scrolling", () => {
    const { container } = render(
      <MemoryRouter>
        <DaySection
          date="2026-05-24"
          episodes={[]}
          isToday={false}
          myShowsOnly={false}
        />
      </MemoryRouter>,
    );
    expect(container.querySelector("#day-2026-05-24")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run DaySection
```

Expected: fail.

- [ ] **Step 3: Implement**

Create `frontend/src/features/schedule/DaySection.tsx`:

```tsx
import type { ScheduleWeekEpisode } from "@/types/models";
import { DayBanner } from "./DayBanner";
import { EpisodeRow } from "./EpisodeRow";

export function DaySection({
  date,
  episodes,
  isToday,
  myShowsOnly,
}: {
  date: string;
  episodes: ScheduleWeekEpisode[];
  isToday: boolean;
  myShowsOnly: boolean;
}) {
  const watchlist = episodes.filter((e) => e.on_watchlist);
  const others = myShowsOnly ? [] : episodes.filter((e) => !e.on_watchlist);

  return (
    <section id={`day-${date}`} className="space-y-4">
      <DayBanner date={date} episodes={episodes} isToday={isToday} />
      {watchlist.length > 0 && (
        <div className="space-y-2 rounded-2xl border border-gold/20 bg-gold/[0.025] p-5">
          {watchlist.map((e) => (
            <EpisodeRow key={`w-${e.id}-${e.type}`} episode={e} />
          ))}
        </div>
      )}
      {watchlist.length > 0 && others.length > 0 && (
        <div className="h-px bg-line" />
      )}
      {others.length > 0 && (
        <div className="space-y-2">
          {others.map((e) => (
            <EpisodeRow key={`o-${e.id}-${e.type}`} episode={e} />
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run DaySection
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/DaySection.tsx frontend/tests/features/DaySection.test.tsx
git commit -m "feat(schedule): DaySection composes banner, watchlist strip, and remainder"
```

---

## Task 15: Frontend — DayStrip component

**Files:**
- Create: `frontend/src/features/schedule/DayStrip.tsx`
- Create: `frontend/tests/features/DayStrip.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/DayStrip.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DayStrip } from "@/features/schedule/DayStrip";

const dates = [
  "2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27",
  "2026-05-28", "2026-05-29", "2026-05-30",
];

describe("DayStrip", () => {
  it("renders 7 chips with weekday labels", () => {
    const noop = () => {};
    render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{ "2026-05-24": 3 }}
        onChipClick={noop}
        onPrevWeek={noop}
        onNextWeek={noop}
      />,
    );
    ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].forEach((d) =>
      expect(screen.getByText(d)).toBeInTheDocument(),
    );
    dates.forEach((d) => {
      const dayNum = Number(d.split("-")[2]);
      expect(screen.getAllByText(String(dayNum)).length).toBeGreaterThan(0);
    });
  });

  it("highlights today's chip with data-today=true", () => {
    const noop = () => {};
    const { container } = render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{}}
        onChipClick={noop}
        onPrevWeek={noop}
        onNextWeek={noop}
      />,
    );
    const today = container.querySelector('[data-today="true"]');
    expect(today).not.toBeNull();
    expect(today?.textContent).toContain("26");
  });

  it("fires onChipClick with the clicked date", () => {
    const onChipClick = vi.fn();
    render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{}}
        onChipClick={onChipClick}
        onPrevWeek={() => {}}
        onNextWeek={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("27"));
    expect(onChipClick).toHaveBeenCalledWith("2026-05-27");
  });

  it("fires prev/next week handlers from chevrons", () => {
    const onPrevWeek = vi.fn();
    const onNextWeek = vi.fn();
    render(
      <DayStrip
        weekStart="2026-05-24"
        todayIso="2026-05-26"
        episodeCounts={{}}
        onChipClick={() => {}}
        onPrevWeek={onPrevWeek}
        onNextWeek={onNextWeek}
      />,
    );
    fireEvent.click(screen.getByLabelText(/previous week/i));
    fireEvent.click(screen.getByLabelText(/next week/i));
    expect(onPrevWeek).toHaveBeenCalled();
    expect(onNextWeek).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test, confirm it fails**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run DayStrip
```

Expected: fail.

- [ ] **Step 3: Implement**

Create `frontend/src/features/schedule/DayStrip.tsx`:

```tsx
import { ChevronLeft, ChevronRight } from "lucide-react";
import { formatWeekdayShort, dayNumber } from "./utils";

export function DayStrip({
  weekStart,
  todayIso,
  episodeCounts,
  onChipClick,
  onPrevWeek,
  onNextWeek,
}: {
  weekStart: string;
  todayIso: string;
  episodeCounts: Record<string, number>;
  onChipClick: (date: string) => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
}) {
  const dates: string[] = [];
  for (let i = 0; i < 7; i++) dates.push(shiftDay(weekStart, i));

  const monthLabel = monthOf(weekStart);
  const weekNumber = isoWeekOf(weekStart);

  return (
    <div className="sticky top-0 z-30 -mx-4 px-4 py-[14px] bg-bg/70 backdrop-blur-md backdrop-saturate-150 border-b border-line">
      <div className="flex items-center gap-4">
        <button
          type="button"
          aria-label="previous week"
          onClick={onPrevWeek}
          className="grid h-9 w-9 place-items-center rounded-lg border border-line text-ink-2 hover:text-ink hover:border-line-2 transition"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <div className="hidden sm:flex flex-col items-end border-r border-line-2 pr-4">
          <span className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-peach">
            {monthLabel}
          </span>
          <span className="font-mono text-[11.5px] text-mute">Week {weekNumber}</span>
        </div>

        <div className="grid flex-1 grid-cols-7 gap-2">
          {dates.map((d) => {
            const isToday = d === todayIso;
            const count = episodeCounts[d] ?? 0;
            return (
              <button
                key={d}
                type="button"
                data-today={isToday}
                onClick={() => onChipClick(d)}
                className={[
                  "relative flex flex-col items-center justify-center rounded-xl border px-2.5 py-2 transition",
                  isToday
                    ? "border-peach/60 bg-gradient-to-b from-peach/20 to-peach/[0.06] shadow-[0_0_18px_-2px_rgba(244,182,144,0.45)]"
                    : "border-line bg-row-bg hover:border-peach/30 hover:bg-peach/[0.06] hover:-translate-y-px",
                ].join(" ")}
              >
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-mute">
                  {formatWeekdayShort(d)}
                </span>
                <span
                  className={
                    isToday
                      ? "font-display text-[24px] bg-gradient-to-b from-peach to-peach-deep bg-clip-text text-transparent"
                      : "font-display text-[24px] text-ink"
                  }
                >
                  {dayNumber(d)}
                </span>
                {count > 0 && (
                  <span className="absolute -top-1 right-1 font-mono text-[9px] text-mute bg-bg-elevated rounded px-1">
                    {count}
                  </span>
                )}
                {isToday && (
                  <span className="absolute -bottom-3 font-mono text-[8px] uppercase tracking-[0.2em] text-peach">
                    TODAY
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          aria-label="next week"
          onClick={onNextWeek}
          className="grid h-9 w-9 place-items-center rounded-lg border border-line text-ink-2 hover:text-ink hover:border-line-2 transition"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function shiftDay(weekStart: string, days: number): string {
  const [y, m, d] = weekStart.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

function monthOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).toUpperCase();
}

function isoWeekOf(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const dayNum = dt.getUTCDay() || 7;
  dt.setUTCDate(dt.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(dt.getUTCFullYear(), 0, 1));
  return Math.ceil((((dt.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}
```

- [ ] **Step 4: Run the test, confirm it passes**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run DayStrip
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/DayStrip.tsx frontend/tests/features/DayStrip.test.tsx
git commit -m "feat(schedule): sticky DayStrip with today-chip and week chevrons"
```

---

## Task 16: Frontend — FilterPills component

**Files:**
- Create: `frontend/src/features/schedule/FilterPills.tsx`
- Create: `frontend/tests/features/FilterPills.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/features/FilterPills.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterPills } from "@/features/schedule/FilterPills";

describe("FilterPills", () => {
  it("renders all three lang options and the mine toggle", () => {
    render(
      <FilterPills
        lang="both"
        myShowsOnly={false}
        onLangChange={() => {}}
        onMineToggle={() => {}}
      />,
    );
    ["SUB", "DUB", "BOTH"].forEach((l) =>
      expect(screen.getByText(l)).toBeInTheDocument(),
    );
    expect(screen.getByText(/my shows/i)).toBeInTheDocument();
  });

  it("calls onLangChange with the selected option", () => {
    const onLangChange = vi.fn();
    render(
      <FilterPills
        lang="both"
        myShowsOnly={false}
        onLangChange={onLangChange}
        onMineToggle={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("DUB"));
    expect(onLangChange).toHaveBeenCalledWith("dub");
  });

  it("calls onMineToggle on click", () => {
    const onMineToggle = vi.fn();
    render(
      <FilterPills
        lang="both"
        myShowsOnly={false}
        onLangChange={() => {}}
        onMineToggle={onMineToggle}
      />,
    );
    fireEvent.click(screen.getByText(/my shows/i));
    expect(onMineToggle).toHaveBeenCalled();
  });

  it("marks the active lang with data-active=true", () => {
    const { container } = render(
      <FilterPills
        lang="sub"
        myShowsOnly={false}
        onLangChange={() => {}}
        onMineToggle={() => {}}
      />,
    );
    const active = container.querySelector('[data-active="true"]');
    expect(active?.textContent).toBe("SUB");
  });
});
```

- [ ] **Step 2: Run, confirm fail**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run FilterPills
```

Expected: fail.

- [ ] **Step 3: Implement**

Create `frontend/src/features/schedule/FilterPills.tsx`:

```tsx
import { Star } from "lucide-react";

type Lang = "sub" | "dub" | "both";
const OPTIONS: Lang[] = ["sub", "dub", "both"];

export function FilterPills({
  lang,
  myShowsOnly,
  onLangChange,
  onMineToggle,
}: {
  lang: Lang;
  myShowsOnly: boolean;
  onLangChange: (v: Lang) => void;
  onMineToggle: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="inline-flex rounded-lg border border-line bg-row-bg p-1">
        {OPTIONS.map((opt) => {
          const active = opt === lang;
          return (
            <button
              key={opt}
              type="button"
              data-active={active}
              onClick={() => onLangChange(opt)}
              className={[
                "px-3 py-1 rounded-md font-mono text-[11px] uppercase tracking-[0.16em] transition",
                active ? "bg-peach/15 text-peach" : "text-ink-2 hover:text-ink",
              ].join(" ")}
            >
              {opt.toUpperCase()}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={onMineToggle}
        data-active={myShowsOnly}
        className={[
          "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] transition",
          myShowsOnly
            ? "border-gold/40 bg-gold/[0.08] text-gold"
            : "border-line bg-row-bg text-ink-2 hover:text-ink hover:border-line-2",
        ].join(" ")}
      >
        <Star className="h-3 w-3" fill={myShowsOnly ? "currentColor" : "none"} />
        My shows
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Run, confirm pass**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run FilterPills
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```
git add frontend/src/features/schedule/FilterPills.tsx frontend/tests/features/FilterPills.test.tsx
git commit -m "feat(schedule): FilterPills segmented control + My shows toggle"
```

---

## Task 17: Frontend — ScheduleHeader component

**Files:**
- Create: `frontend/src/features/schedule/ScheduleHeader.tsx`
- (No dedicated test file — its behavior is covered by SchedulePage.test.tsx in Task 18.)

- [ ] **Step 1: Implement**

Create `frontend/src/features/schedule/ScheduleHeader.tsx`:

```tsx
import { FilterPills } from "./FilterPills";

type Lang = "sub" | "dub" | "both";

export function ScheduleHeader({
  lang,
  myShowsOnly,
  onLangChange,
  onMineToggle,
}: {
  lang: Lang;
  myShowsOnly: boolean;
  onLangChange: (v: Lang) => void;
  onMineToggle: () => void;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between pt-14 pb-7">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-peach">
          The release calendar
        </p>
        <h1 className="font-display italic text-[clamp(48px,5vw,76px)] leading-none tracking-tight">
          <span className="bg-gradient-to-b from-ink to-ink-2 bg-clip-text text-transparent">
            What's
          </span>{" "}
          <span className="bg-gradient-to-b from-peach to-peach-deep bg-clip-text text-transparent">
            airing
          </span>
        </h1>
      </div>
      <FilterPills
        lang={lang}
        myShowsOnly={myShowsOnly}
        onLangChange={onLangChange}
        onMineToggle={onMineToggle}
      />
    </header>
  );
}
```

- [ ] **Step 2: Verify tsc**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/tsc -b
```

Expected: no errors.

- [ ] **Step 3: Commit**

```
git add frontend/src/features/schedule/ScheduleHeader.tsx
git commit -m "feat(schedule): ScheduleHeader page title + filter controls"
```

---

## Task 18: Frontend — SchedulePage rewrite (URL state + today scroll)

**Files:**
- Delete: `frontend/src/features/schedule/ScheduleCalendar.tsx`
- Delete: `frontend/src/features/schedule/ScheduleEpisodeRow.tsx`
- Rewrite: `frontend/src/features/schedule/SchedulePage.tsx`
- Rewrite: `frontend/tests/features/SchedulePage.test.tsx`

- [ ] **Step 1: Write the rewritten page test**

Replace `frontend/tests/features/SchedulePage.test.tsx` entirely with:

```tsx
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const useScheduleWeekMock = vi.hoisted(() => vi.fn());
vi.mock("@/hooks/useScheduleWeek", () => ({
  useScheduleWeek: useScheduleWeekMock,
}));

import { SchedulePage } from "@/features/schedule/SchedulePage";
import { useAuth } from "@/stores/auth";

const fakeUser = {
  id: 1,
  email: "a@b.c",
  username: "u",
  display_name: null,
  avatar_url: null,
  bio: null,
  created_at: "2026-01-01",
};

const sevenEmptyDays = (weekStart: string) => {
  const out = [];
  const [y, m, d] = weekStart.split("-").map(Number);
  for (let i = 0; i < 7; i++) {
    const dt = new Date(Date.UTC(y, m - 1, d + i));
    out.push({ date: dt.toISOString().slice(0, 10), episodes: [] });
  }
  return out;
};

beforeEach(() => {
  useScheduleWeekMock.mockReset();
  useAuth.setState({ user: fakeUser, status: "ready" });
});

describe("SchedulePage", () => {
  it("renders the sign-in prompt when unauthenticated", () => {
    useAuth.setState({ user: null, status: "idle" });
    useScheduleWeekMock.mockReturnValue({ isLoading: false, data: undefined });
    render(
      <MemoryRouter initialEntries={["/schedule"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/sign in to see the schedule/i)).toBeInTheDocument();
  });

  it("renders the header, day strip, and 7 sections when data loads", () => {
    useScheduleWeekMock.mockReturnValue({
      isLoading: false,
      data: { week_start: "2026-05-24", days: sevenEmptyDays("2026-05-24") },
    });
    const { container } = render(
      <MemoryRouter initialEntries={["/schedule?week=2026-05-24"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/what's/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/previous week/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/next week/i)).toBeInTheDocument();
    expect(container.querySelectorAll('section[id^="day-"]').length).toBe(7);
  });

  it("renders skeletons while loading", () => {
    useScheduleWeekMock.mockReturnValue({ isLoading: true, data: undefined });
    const { container } = render(
      <MemoryRouter initialEntries={["/schedule?week=2026-05-24"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(container.querySelectorAll('[data-skeleton="true"]').length).toBeGreaterThan(0);
  });

  it("passes lang and mine from URL into useScheduleWeek", () => {
    useScheduleWeekMock.mockReturnValue({
      isLoading: false,
      data: { week_start: "2026-05-24", days: sevenEmptyDays("2026-05-24") },
    });
    render(
      <MemoryRouter initialEntries={["/schedule?week=2026-05-24&lang=dub&mine=1"]}>
        <SchedulePage />
      </MemoryRouter>,
    );
    expect(useScheduleWeekMock).toHaveBeenCalledWith("2026-05-24", "dub", true);
  });
});
```

- [ ] **Step 2: Delete the old files**

```
rm frontend/src/features/schedule/ScheduleCalendar.tsx
rm frontend/src/features/schedule/ScheduleEpisodeRow.tsx
```

- [ ] **Step 3: Rewrite SchedulePage**

Replace `frontend/src/features/schedule/SchedulePage.tsx` entirely with:

```tsx
import { useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useScheduleWeek } from "@/hooks/useScheduleWeek";
import { ScheduleHeader } from "./ScheduleHeader";
import { DayStrip } from "./DayStrip";
import { DaySection } from "./DaySection";
import { getSundayOfWeek, shiftWeek, todayIsoDate } from "./utils";

type Lang = "sub" | "dub" | "both";

export function SchedulePage() {
  const user = useAuth((s) => s.user);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const week = params.get("week");
  const lang = (params.get("lang") as Lang) || "both";
  const mine = params.get("mine") === "1";

  // Canonicalize: if no ?week, redirect to today's Sunday.
  useEffect(() => {
    if (!week) {
      const sun = getSundayOfWeek(new Date());
      const p = new URLSearchParams(params);
      p.set("week", sun);
      navigate({ search: `?${p}` }, { replace: true });
    }
  }, [week, navigate, params]);

  const today = todayIsoDate();
  const q = useScheduleWeek(week ?? getSundayOfWeek(new Date()), lang, mine);

  const episodeCounts = useMemo(() => {
    const out: Record<string, number> = {};
    if (!q.data) return out;
    for (const d of q.data.days) out[d.date] = d.episodes.length;
    return out;
  }, [q.data]);

  // Today auto-scroll: once on mount when data is available and today is in view.
  useEffect(() => {
    if (!q.data) return;
    const target = document.getElementById(`day-${today}`);
    if (target) target.scrollIntoView({ behavior: "auto", block: "start" });
    // run only once when the data first arrives for this week
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Boolean(q.data), q.data?.week_start]);

  function setLang(next: Lang) {
    const p = new URLSearchParams(params);
    p.set("lang", next);
    setParams(p, { replace: true });
  }

  function toggleMine() {
    const p = new URLSearchParams(params);
    p.set("mine", mine ? "0" : "1");
    setParams(p, { replace: true });
  }

  function shift(weeks: number) {
    if (!week) return;
    const next = shiftWeek(week, weeks);
    const p = new URLSearchParams(params);
    p.set("week", next);
    setParams(p, { replace: true });
  }

  function scrollToDay(date: string) {
    const target = document.getElementById(`day-${date}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display italic text-4xl mb-2">Sign in to see the schedule</h1>
        <p className="text-text-muted">
          Track sub and dub episode releases for shows you're following.
        </p>
      </div>
    );
  }

  return (
    <div>
      <ScheduleHeader
        lang={lang}
        myShowsOnly={mine}
        onLangChange={setLang}
        onMineToggle={toggleMine}
      />
      <DayStrip
        weekStart={week ?? getSundayOfWeek(new Date())}
        todayIso={today}
        episodeCounts={episodeCounts}
        onChipClick={scrollToDay}
        onPrevWeek={() => shift(-1)}
        onNextWeek={() => shift(1)}
      />
      <div className="mt-10 space-y-14">
        {q.isLoading || !q.data
          ? Array.from({ length: 7 }).map((_, i) => (
              <div key={i} data-skeleton="true" className="space-y-3">
                <Skeleton className="h-[232px] rounded-[22px]" />
                <Skeleton className="h-24 rounded-lg" />
              </div>
            ))
          : q.data.days.map((d) => (
              <DaySection
                key={d.date}
                date={d.date}
                episodes={d.episodes}
                isToday={d.date === today}
                myShowsOnly={mine}
              />
            ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the page test**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/vitest run SchedulePage
```

Expected: 4 passed.

- [ ] **Step 5: Run the full vitest + tsc**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/tsc -b && ./node_modules/.bin/vitest run
```

Expected: tsc clean, all vitest tests pass (the old ScheduleCalendar/ScheduleEpisodeRow tests are gone with the files).

- [ ] **Step 6: Commit**

```
git add frontend/src/features/schedule/ frontend/tests/features/SchedulePage.test.tsx
git commit -m "feat(schedule): rewrite SchedulePage on URL state with new component tree"
```

---

## Task 19: Frontend — Update E2E demo script

**Files:**
- Modify: `frontend/e2e/demo/06-schedule.spec.ts`

- [ ] **Step 1: Read the existing spec and update selectors**

The old spec asserted on the legacy layout. Rewrite assertions to match the new chrome. Replace the file contents with:

```ts
import { test, expect } from "@playwright/test";
import { loginAsDemo } from "../helpers/auth";

test("schedule page renders the new week board", async ({ page }) => {
  await loginAsDemo(page);
  await page.goto("/schedule");

  // Header is present
  await expect(page.getByText(/what's/i).first()).toBeVisible();

  // Day strip has 7 chips
  await expect(page.locator('button[data-today], button[data-today="true"], button[data-today="false"]')).toHaveCount(7);

  // Filter pills exist
  await expect(page.getByText(/SUB/).first()).toBeVisible();
  await expect(page.getByText(/DUB/).first()).toBeVisible();
  await expect(page.getByText(/BOTH/).first()).toBeVisible();

  // 7 day sections render
  await expect(page.locator('section[id^="day-"]')).toHaveCount(7);
});
```

If `loginAsDemo` doesn't exist in this repo, inline whatever auth pattern the other specs use (check `frontend/e2e/demo/01-*.spec.ts` for reference).

- [ ] **Step 2: Run the spec (skip if Playwright not configured locally)**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/playwright test e2e/demo/06-schedule.spec.ts
```

Expected: passes if the demo server is reachable. If the local Playwright config requires a running server, document the dependency in the commit message instead of forcing the run.

- [ ] **Step 3: Commit**

```
git add frontend/e2e/demo/06-schedule.spec.ts
git commit -m "test(schedule): update E2E demo spec for new layout"
```

---

## Task 20: Final verification

**Files:** none (test runs only)

- [ ] **Step 1: Backend full suite**

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe -m pytest --tb=short -q
```

Expected: every test passes — the prior 272 plus the 15 new `test_schedule_week.py` cases (≥287 total).

- [ ] **Step 2: Frontend full suite**

```
cd C:/Users/parus/Downloads/bingery-update/frontend && ./node_modules/.bin/tsc -b && ./node_modules/.bin/vitest run
```

Expected: tsc clean; all vitest tests pass (prior 40 plus 7 new suites — Badge, EstimatedTag, EpisodeRow, DayBanner, DaySection, DayStrip, FilterPills, plus the rewritten SchedulePage and scheduleUtils).

- [ ] **Step 3: Local manual smoke (Flask + Vite)**

Start Flask:

```
C:/Users/parus/AppData/Local/Microsoft/WindowsApps/python.exe app.py
```

In another shell, start Vite:

```
cd C:/Users/parus/Downloads/bingery-update/frontend && npm run dev
```

Log in as the demo user, navigate to `/schedule`. Confirm:
- URL gets canonicalized to `?week=<Sunday>` on first load.
- Today's chip is highlighted; today's section scrolls into view.
- Switching Sub/Dub/Both updates the URL and the rows.
- ★ My shows toggle restricts the view.
- Prev/next week chevrons swap the visible week.

- [ ] **Step 4: Final commit (only if anything was tweaked during verification)**

```
git status
# if dirty:
git add -A && git commit -m "chore(schedule): verification fixups"
```

- [ ] **Step 5: Push**

```
git push origin main
```

(Or open a PR if working on a feature branch — see your standard workflow.)
