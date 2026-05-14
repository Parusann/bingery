"""Tests for /api/schedule/upcoming and /api/anime/<id>/episodes (Plan 4 A3)."""

from datetime import datetime, timedelta, timezone


# ─── Helpers ────────────────────────────────────────────────────────────────


def _today_utc_midnight() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _seed_anime(app, **kwargs):
    """Seed a single Anime row, returning its id."""
    from models import db, Anime

    defaults = dict(
        title="Test Anime",
        title_english=None,
        synopsis="",
        year=2026,
        season="spring",
        episodes=12,
        studio="Studio",
        image_url="https://example.com/cover.jpg",
        source="ORIGINAL",
        status="RELEASING",
    )
    defaults.update(kwargs)
    with app.app_context():
        a = Anime(**defaults)
        db.session.add(a)
        db.session.commit()
        return a.id


def _seed_episode(app, *, anime_id, episode_number, air_sub=None, air_dub=None):
    """Seed an Episode row. air_sub/air_dub may be naive or aware datetimes."""
    from models import db, Episode

    def _strip(dt):
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    with app.app_context():
        e = Episode(
            anime_id=anime_id,
            episode_number=episode_number,
            air_date_sub=_strip(air_sub),
            air_date_dub=_strip(air_dub),
        )
        db.session.add(e)
        db.session.commit()
        return e.id


# ─── /api/schedule/upcoming ────────────────────────────────────────────────


def test_upcoming_requires_auth(client):
    r = client.get("/api/schedule/upcoming")
    assert r.status_code == 401


def test_upcoming_default_days_and_kind(client, auth_headers, app):
    headers, _ = auth_headers
    r = client.get("/api/schedule/upcoming", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert "days" in body
    assert len(body["days"]) == 7
    today = _today_utc_midnight().date().isoformat()
    assert body["days"][0]["date"] == today


def test_upcoming_days_clamping(client, auth_headers):
    headers, _ = auth_headers

    r = client.get("/api/schedule/upcoming?days=0", headers=headers)
    assert r.status_code == 200
    assert len(r.get_json()["days"]) == 1

    r = client.get("/api/schedule/upcoming?days=999", headers=headers)
    assert r.status_code == 200
    assert len(r.get_json()["days"]) == 30

    r = client.get("/api/schedule/upcoming?days=abc", headers=headers)
    assert r.status_code == 200
    assert len(r.get_json()["days"]) == 7


def test_upcoming_kind_validation(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/schedule/upcoming?kind=invalid", headers=headers)
    assert r.status_code == 400
    assert "sub/dub/both" in r.get_json()["error"]


def test_upcoming_sub_filter(client, auth_headers, app):
    headers, _ = auth_headers
    base = _today_utc_midnight()
    aid = _seed_anime(app, title="Show Sub", title_english="Show Sub EN")

    in_window = base + timedelta(days=2, hours=10)
    out_window = base + timedelta(days=15)
    past = base - timedelta(days=1)

    _seed_episode(app, anime_id=aid, episode_number=1, air_sub=in_window)
    _seed_episode(app, anime_id=aid, episode_number=2, air_sub=out_window)
    _seed_episode(app, anime_id=aid, episode_number=3, air_sub=past)

    r = client.get("/api/schedule/upcoming?days=7&kind=sub", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    all_eps = [e for d in body["days"] for e in d["episodes"]]
    nums = [e["episode_number"] for e in all_eps]
    assert nums == [1]
    assert all_eps[0]["kind"] == "sub"
    assert all_eps[0]["anime"]["title"] == "Show Sub EN"
    assert all_eps[0]["anime"]["image_url"] == "https://example.com/cover.jpg"


def test_upcoming_dub_filter(client, auth_headers, app):
    headers, _ = auth_headers
    base = _today_utc_midnight()
    aid = _seed_anime(app, title="Show Dub")

    in_window = base + timedelta(days=3, hours=8)
    out_window = base + timedelta(days=20)

    _seed_episode(app, anime_id=aid, episode_number=1, air_dub=in_window)
    _seed_episode(app, anime_id=aid, episode_number=2, air_dub=out_window)
    # An episode with only sub date should NOT appear in dub query.
    _seed_episode(app, anime_id=aid, episode_number=3, air_sub=in_window)

    r = client.get("/api/schedule/upcoming?days=7&kind=dub", headers=headers)
    body = r.get_json()
    all_eps = [e for d in body["days"] for e in d["episodes"]]
    nums = [e["episode_number"] for e in all_eps]
    assert nums == [1]
    assert all_eps[0]["kind"] == "dub"


def test_upcoming_both_emits_both_kinds(client, auth_headers, app):
    headers, _ = auth_headers
    base = _today_utc_midnight()
    aid = _seed_anime(app, title="Both Show")

    sub_time = base + timedelta(days=1, hours=12)
    dub_time = base + timedelta(days=4, hours=9)
    _seed_episode(
        app, anime_id=aid, episode_number=5, air_sub=sub_time, air_dub=dub_time
    )

    r = client.get("/api/schedule/upcoming?days=7&kind=both", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    flat = [e for d in body["days"] for e in d["episodes"]]
    assert len(flat) == 2
    kinds = sorted(e["kind"] for e in flat)
    assert kinds == ["dub", "sub"]
    # Both should reference the same Episode row.
    assert {e["id"] for e in flat} == {e["id"] for e in flat}
    assert all(e["episode_number"] == 5 for e in flat)


def test_upcoming_empty_days_included(client, auth_headers, app):
    headers, _ = auth_headers
    base = _today_utc_midnight()
    aid = _seed_anime(app, title="One Day Show")
    _seed_episode(
        app,
        anime_id=aid,
        episode_number=1,
        air_sub=base + timedelta(days=2, hours=10),
    )

    r = client.get("/api/schedule/upcoming?days=5&kind=sub", headers=headers)
    body = r.get_json()
    assert len(body["days"]) == 5
    expected_dates = [
        (base + timedelta(days=i)).date().isoformat() for i in range(5)
    ]
    assert [d["date"] for d in body["days"]] == expected_dates
    # Only day index 2 has an episode; the others are empty lists.
    for i, day in enumerate(body["days"]):
        if i == 2:
            assert len(day["episodes"]) == 1
        else:
            assert day["episodes"] == []


def test_upcoming_episodes_sorted_within_day(client, auth_headers, app):
    headers, _ = auth_headers
    base = _today_utc_midnight()

    aid_b = _seed_anime(app, title="Bravo", title_english="Bravo")
    aid_a = _seed_anime(app, title="Alpha", title_english="Alpha")
    aid_c = _seed_anime(app, title="Charlie", title_english="Charlie")

    same_day = base + timedelta(days=1)
    # All air on the same day. Times chosen so:
    #   Alpha 09:00, Bravo 09:00 (tie -> title), Charlie 14:00
    _seed_episode(
        app,
        anime_id=aid_b,
        episode_number=1,
        air_sub=same_day + timedelta(hours=9),
    )
    _seed_episode(
        app,
        anime_id=aid_a,
        episode_number=1,
        air_sub=same_day + timedelta(hours=9),
    )
    _seed_episode(
        app,
        anime_id=aid_c,
        episode_number=1,
        air_sub=same_day + timedelta(hours=14),
    )

    r = client.get("/api/schedule/upcoming?days=3&kind=sub", headers=headers)
    body = r.get_json()
    day1 = body["days"][1]
    titles = [e["anime"]["title"] for e in day1["episodes"]]
    assert titles == ["Alpha", "Bravo", "Charlie"]


# ─── /api/anime/<id>/episodes ──────────────────────────────────────────────


def test_anime_episodes_requires_auth(client, app):
    aid = _seed_anime(app, title="No Auth")
    r = client.get(f"/api/anime/{aid}/episodes")
    assert r.status_code == 401


def test_anime_episodes_not_found(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/anime/9999999/episodes", headers=headers)
    assert r.status_code == 404
    assert r.get_json()["error"] == "anime not found"


def test_anime_episodes_returns_all_sorted(client, auth_headers, app):
    headers, _ = auth_headers
    aid = _seed_anime(app, title="All Eps")
    base = _today_utc_midnight()
    _seed_episode(app, anime_id=aid, episode_number=3, air_sub=base + timedelta(days=20))
    _seed_episode(app, anime_id=aid, episode_number=1, air_sub=base + timedelta(days=6))
    _seed_episode(app, anime_id=aid, episode_number=2, air_sub=base + timedelta(days=13))

    r = client.get(f"/api/anime/{aid}/episodes", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    nums = [e["episode_number"] for e in body["episodes"]]
    assert nums == [1, 2, 3]
    # Shape contract for each row.
    for e in body["episodes"]:
        assert set(e.keys()) == {"id", "episode_number", "air_date_sub", "air_date_dub"}


def test_anime_episodes_next_sub(client, auth_headers, app):
    headers, _ = auth_headers
    aid = _seed_anime(app, title="Next Sub")
    base = _today_utc_midnight()

    _seed_episode(app, anime_id=aid, episode_number=1, air_sub=base - timedelta(days=7))
    _seed_episode(app, anime_id=aid, episode_number=2, air_sub=base + timedelta(days=2))
    _seed_episode(app, anime_id=aid, episode_number=3, air_sub=base + timedelta(days=9))

    r = client.get(f"/api/anime/{aid}/episodes", headers=headers)
    body = r.get_json()
    assert body["next_sub"] is not None
    assert body["next_sub"]["episode_number"] == 2


def test_anime_episodes_next_dub_separate_from_sub(client, auth_headers, app):
    headers, _ = auth_headers
    aid = _seed_anime(app, title="Sub vs Dub")
    base = _today_utc_midnight()

    # Ep1: sub upcoming, dub past.
    _seed_episode(
        app,
        anime_id=aid,
        episode_number=1,
        air_sub=base + timedelta(days=3),
        air_dub=base - timedelta(days=30),
    )
    # Ep2: sub past, dub upcoming.
    _seed_episode(
        app,
        anime_id=aid,
        episode_number=2,
        air_sub=base - timedelta(days=14),
        air_dub=base + timedelta(days=10),
    )

    r = client.get(f"/api/anime/{aid}/episodes", headers=headers)
    body = r.get_json()
    assert body["next_sub"]["episode_number"] == 1
    assert body["next_dub"]["episode_number"] == 2


def test_anime_episodes_no_upcoming_returns_null(client, auth_headers, app):
    headers, _ = auth_headers
    aid = _seed_anime(app, title="All Past")
    base = _today_utc_midnight()

    _seed_episode(
        app,
        anime_id=aid,
        episode_number=1,
        air_sub=base - timedelta(days=30),
        air_dub=base - timedelta(days=20),
    )
    _seed_episode(
        app,
        anime_id=aid,
        episode_number=2,
        air_sub=base - timedelta(days=14),
        air_dub=base - timedelta(days=5),
    )

    r = client.get(f"/api/anime/{aid}/episodes", headers=headers)
    body = r.get_json()
    assert body["next_sub"] is None
    assert body["next_dub"] is None
    assert len(body["episodes"]) == 2
