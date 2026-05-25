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


def _auth(app, user_id):
    """Generate a header dict carrying a valid JWT for the given user_id."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=str(user_id))
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


def test_on_watchlist_includes_dropped_status(client, app, user, airing_data):
    """Any WatchlistEntry status should flag on_watchlist=True (not just 'watching')."""
    with app.app_context():
        we = WatchlistEntry(
            user_id=user["id"],
            anime_id=airing_data["a1_id"],
            status="dropped",
        )
        db.session.add(we)
        db.session.commit()

    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    body = res.get_json()
    all_eps = [e for d in body["days"] for e in d["episodes"]]
    target = next(e for e in all_eps if e["anime_id"] == airing_data["a1_id"])
    assert target["on_watchlist"] is True
