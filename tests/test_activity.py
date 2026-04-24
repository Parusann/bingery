"""Tests for /api/activity endpoints."""
from datetime import datetime, timedelta


def _seed_activity(app, user_id):
    from models import db, Anime, Rating, FanGenreVote, WatchlistEntry
    with app.app_context():
        a = Anime(
            mal_id=1, title="Frieren", synopsis="", year=2023,
            episodes=28, studio="Madhouse", image_url="",
            source="MANGA", status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        r = Rating(user_id=user_id, anime_id=a.id, score=9, review="lovely")
        v = FanGenreVote(user_id=user_id, anime_id=a.id, genre_tag="Tearjerker")
        w = WatchlistEntry(user_id=user_id, anime_id=a.id, status="completed")
        db.session.add_all([r, v, w])
        db.session.commit()


def test_activity_feed_returns_recent_actions(client, auth_headers, app):
    headers, user = auth_headers
    _seed_activity(app, user.id)

    r = client.get("/api/activity?limit=10", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    kinds = {item["type"] for item in body["items"]}
    assert {"rating", "genre_vote", "status"}.issubset(kinds)

    for item in body["items"]:
        assert "anime_id" in item
        assert "anime_title" in item
        assert "timestamp" in item


def test_activity_feed_respects_limit(client, auth_headers, app):
    headers, user = auth_headers
    _seed_activity(app, user.id)
    r = client.get("/api/activity?limit=1", headers=headers)
    assert r.status_code == 200
    assert len(r.get_json()["items"]) == 1


def test_activity_requires_auth(client):
    r = client.get("/api/activity")
    assert r.status_code == 401
