"""Tests for /api/anime routes — param hygiene."""
from models import db, Anime, Rating


def test_top_negative_limit_clamped(client, app, auth_headers):
    _headers, user = auth_headers
    with app.app_context():
        a1 = Anime(title="A1", anilist_id=7001)
        a2 = Anime(title="A2", anilist_id=7002)
        db.session.add_all([a1, a2])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user.id, anime_id=a1.id, score=9),
            Rating(user_id=user.id, anime_id=a2.id, score=8),
        ])
        db.session.commit()

    r = client.get("/api/anime/top?limit=-5")
    assert r.status_code == 200
    # Negative limits must clamp to at least 1 row, never "no limit".
    assert len(r.get_json()["top_anime"]) == 1
