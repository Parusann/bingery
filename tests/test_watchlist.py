"""Tests for /api/watchlist — input validation, score sort, upsert race."""
from datetime import datetime, timedelta

from models import db, Anime, WatchlistEntry


def _anime(title, anilist_id, api_score=8.0):
    a = Anime(title=title, anilist_id=anilist_id, api_score=api_score)
    db.session.add(a)
    db.session.commit()
    return a


def test_set_status_rejects_non_numeric_episodes_on_update(client, app, auth_headers):
    headers, _user = auth_headers
    with app.app_context():
        aid = _anime("Show", 21001).id
    client.post(f"/api/watchlist/anime/{aid}", json={"status": "watching"}, headers=headers)
    r = client.post(
        f"/api/watchlist/anime/{aid}",
        json={"status": "watching", "episodes_watched": "abc"},
        headers=headers,
    )
    assert r.status_code == 400


def test_set_status_rejects_non_numeric_episodes_on_create(client, app, auth_headers):
    headers, _user = auth_headers
    with app.app_context():
        aid = _anime("Show2", 21002).id
    r = client.post(
        f"/api/watchlist/anime/{aid}",
        json={"status": "watching", "episodes_watched": {"x": 1}},
        headers=headers,
    )
    assert r.status_code == 400


def test_set_status_clamps_negative_episodes_on_create(client, app, auth_headers):
    headers, _user = auth_headers
    with app.app_context():
        aid = _anime("Show3", 21003).id
    r = client.post(
        f"/api/watchlist/anime/{aid}",
        json={"status": "watching", "episodes_watched": -5},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.get_json()["entry"]["episodes_watched"] == 0


def test_sort_by_score_orders_by_anime_score(client, app, auth_headers):
    headers, _user = auth_headers
    with app.app_context():
        low_id = _anime("Low", 21004, api_score=6.0).id
        high_id = _anime("High", 21005, api_score=9.0).id

    client.post(f"/api/watchlist/anime/{high_id}", json={"status": "watching"}, headers=headers)
    client.post(f"/api/watchlist/anime/{low_id}", json={"status": "watching"}, headers=headers)

    # Make the low-score entry the most recently updated, so the buggy
    # updated_at ordering would put it first.
    with app.app_context():
        e = db.session.query(WatchlistEntry).filter_by(anime_id=low_id).first()
        e.updated_at = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()

    r = client.get("/api/watchlist?sort=score", headers=headers)
    assert r.status_code == 200
    titles = [e["anime"]["title"] for e in r.get_json()["entries"]]
    assert titles == ["High", "Low"]


def test_concurrent_first_write_does_not_500(client, app, auth_headers, monkeypatch):
    """Two simultaneous first-writes for one (user, anime): the loser's
    INSERT collides on the unique constraint; it must apply its update to
    the winner's row instead of crashing with a 500."""
    from sqlalchemy.exc import IntegrityError

    headers, user = auth_headers
    with app.app_context():
        aid = _anime("Race", 21006).id
        uid = user.id

    real_commit = db.session.commit
    state = {"raced": False}

    def racing_commit():
        if state["raced"]:
            return real_commit()
        state["raced"] = True
        db.session.rollback()
        db.session.add(WatchlistEntry(
            user_id=uid, anime_id=aid, status="completed", episodes_watched=3,
        ))
        real_commit()
        raise IntegrityError(
            "INSERT INTO watchlist_entry", {},
            Exception("UNIQUE constraint failed"),
        )

    monkeypatch.setattr(db.session, "commit", racing_commit)
    r = client.post(f"/api/watchlist/anime/{aid}", json={"status": "watching"}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()["entry"]["status"] == "watching"  # latest write wins


def test_bulk_add_rejects_non_list(client, auth_headers):
    headers, _user = auth_headers
    r = client.post("/api/watchlist/bulk", json={"anime_ids": "nope"}, headers=headers)
    assert r.status_code == 400


def test_bulk_add_happy_path_skips_unknown_ids(client, app, auth_headers):
    headers, _user = auth_headers
    with app.app_context():
        a1 = _anime("B1", 21007).id
        a2 = _anime("B2", 21008).id
    r = client.post(
        "/api/watchlist/bulk",
        json={"anime_ids": [a1, a2, 999999]},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.get_json()["added"] == 2


def test_list_watchlist_does_not_n_plus_one(client, app, auth_headers):
    """Listing a page of entries must batch the per-entry anime / rating /
    fan-vote lookups instead of issuing ~4 queries per entry."""
    from models import db, Anime, Rating, FanGenreVote, WatchlistEntry, Genre

    headers, user = auth_headers
    with app.app_context():
        g = Genre(name="Action", category="standard")
        db.session.add(g)
        for i in range(8):
            a = Anime(title=f"W{i}", anilist_id=41000 + i, api_score=8.0)
            a.official_genres.append(g)
            db.session.add(a)
            db.session.flush()
            db.session.add(WatchlistEntry(user_id=user.id, anime_id=a.id, status="watching"))
            db.session.add(Rating(user_id=user.id, anime_id=a.id, score=8))
            db.session.add(FanGenreVote(user_id=user.id, anime_id=a.id, genre_tag="Action"))
        db.session.commit()

    with app.app_context():
        n = {"c": 0}
        from sqlalchemy import event
        engine = db.engine

        def _before(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                n["c"] += 1

        event.listen(engine, "before_cursor_execute", _before)
        try:
            resp = client.get("/api/watchlist", headers=headers)
        finally:
            event.remove(engine, "before_cursor_execute", _before)

    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["entries"]) == 8
    # Output is preserved: each entry carries anime, score and genres.
    e0 = body["entries"][0]
    assert e0["anime"]["title"].startswith("W")
    assert e0["score"] == 8
    assert e0["genres"] == ["Action"]
    # Batched: query count must not scale with the 8 entries (was ~4 per entry).
    assert n["c"] <= 12, f"expected batched queries, got {n['c']}"


def test_all_param_returns_full_list_with_created_at(client, app, auth_headers):
    headers, user = auth_headers
    with app.app_context():
        for i in range(3):
            a = _anime(f"All Param Show {i}", anilist_id=51000 + i)
            db.session.add(
                WatchlistEntry(user_id=user.id, anime_id=a.id, status="watching")
            )
        db.session.commit()

    # Paginated mode still caps results.
    paged = client.get("/api/watchlist?per_page=2", headers=headers).get_json()
    assert len(paged["entries"]) == 2
    assert paged["total"] == 3

    # all=1 returns every entry, unpaginated, each carrying created_at.
    full = client.get("/api/watchlist?all=1", headers=headers).get_json()
    assert len(full["entries"]) == 3
    assert full["total"] == 3
    assert all("created_at" in e for e in full["entries"])
