"""Tests for /api/anime/<id>/rate and /review — data-preservation rules."""
from models import db, Anime, FanGenreVote


def _anime(app, anilist_id=22001):
    with app.app_context():
        a = Anime(title="Rated Show", anilist_id=anilist_id, api_score=8.0)
        db.session.add(a)
        db.session.commit()
        return a.id


def test_rerate_without_review_key_keeps_review(client, app, auth_headers):
    """A score-only re-rate (star widget) must not wipe an existing review."""
    headers, _user = auth_headers
    aid = _anime(app)
    r = client.post(
        f"/api/anime/{aid}/rate",
        json={"score": 8, "review": "A thoughtful review."},
        headers=headers,
    )
    assert r.status_code == 200
    r = client.post(f"/api/anime/{aid}/rate", json={"score": 9}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()["rating"]["review"] == "A thoughtful review."


def test_full_review_without_genres_key_keeps_votes(client, app, auth_headers):
    """Re-submitting a review without the genres key must not wipe the
    user's existing fan-genre votes."""
    headers, _user = auth_headers
    aid = _anime(app, anilist_id=22002)
    r = client.post(
        f"/api/anime/{aid}/review",
        json={"score": 8, "genres": ["Action"]},
        headers=headers,
    )
    assert r.status_code == 200
    r = client.post(f"/api/anime/{aid}/review", json={"score": 9}, headers=headers)
    assert r.status_code == 200
    votes = db.session.query(FanGenreVote).filter_by(anime_id=aid).all()
    assert [v.genre_tag for v in votes] == ["Action"]


def test_full_review_rejects_invalid_genres_shape(client, app, auth_headers):
    """An invalid genres payload must 400, not be silently ignored."""
    headers, _user = auth_headers
    aid = _anime(app, anilist_id=22003)
    r = client.post(
        f"/api/anime/{aid}/review",
        json={"score": 8, "genres": "Action"},
        headers=headers,
    )
    assert r.status_code == 400


def test_full_review_without_review_key_keeps_review(client, app, auth_headers):
    headers, _user = auth_headers
    aid = _anime(app, anilist_id=22004)
    r = client.post(
        f"/api/anime/{aid}/review",
        json={"score": 8, "review": "Kept."},
        headers=headers,
    )
    assert r.status_code == 200
    r = client.post(f"/api/anime/{aid}/review", json={"score": 9}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()["rating"]["review"] == "Kept."
