"""Tests for /api/anime/<id>/episodes (Plan 4 A3) and the dub_estimated flag."""

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


def _seed_episode(
    app, *, anime_id, episode_number, air_sub=None, air_dub=None, dub_source=None
):
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
            dub_source=dub_source,
        )
        db.session.add(e)
        db.session.commit()
        return e.id


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
        assert set(e.keys()) == {
            "id",
            "episode_number",
            "air_date_sub",
            "air_date_dub",
            "dub_source",
            "dub_estimated",
        }


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


def test_anime_episodes_dub_estimated_flag(client, auth_headers, app):
    """A synthetic dub date is flagged estimated; a real-source one is not."""
    headers, _ = auth_headers
    aid = _seed_anime(app, title="Estimated Mix")
    base = _today_utc_midnight()

    # Synthetic projection → estimated. Earliest upcoming dub so it drives next_dub.
    _seed_episode(
        app,
        anime_id=aid,
        episode_number=1,
        air_sub=base + timedelta(days=1),
        air_dub=base + timedelta(days=4),
        dub_source="synthetic_lag_8w",
    )
    # Real source → not estimated.
    _seed_episode(
        app,
        anime_id=aid,
        episode_number=2,
        air_sub=base + timedelta(days=2),
        air_dub=base + timedelta(days=10),
        dub_source="crunchyroll_rss",
    )
    # Sub-only episode → no dub, not estimated.
    _seed_episode(app, anime_id=aid, episode_number=3, air_sub=base + timedelta(days=3))

    r = client.get(f"/api/anime/{aid}/episodes", headers=headers)
    body = r.get_json()
    by_num = {e["episode_number"]: e for e in body["episodes"]}
    assert by_num[1]["dub_estimated"] is True
    assert by_num[1]["dub_source"] == "synthetic_lag_8w"
    assert by_num[2]["dub_estimated"] is False
    assert by_num[2]["dub_source"] == "crunchyroll_rss"
    assert by_num[3]["dub_estimated"] is False
    assert by_num[3]["dub_source"] is None

    # next_dub carries the same provenance fields (ep 1 is the earliest dub).
    assert body["next_dub"]["episode_number"] == 1
    assert body["next_dub"]["dub_estimated"] is True
