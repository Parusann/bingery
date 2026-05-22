"""Tests for /api/recommend/* endpoints."""
from unittest.mock import patch


def test_for_me_uses_signal_engine_shape(client, app, auth_headers):
    """/for-me returns the legacy {recommendations, taste_profile, source} shape
    but uses the new signal engine: relevance_score is in [0, 1], not 0-100."""
    from models import db, Anime, Rating
    headers, user = auth_headers
    with app.app_context():
        # Seed a rating so we hit the personalized branch (not popular fallback)
        rated = Anime(title="Already Loved", anilist_id=4000, api_score=9.0, studio="MAPPA")
        db.session.add(rated); db.session.commit()
        db.session.add(Rating(user_id=user.id, anime_id=rated.id, score=9))
        # And two unrated candidates
        db.session.add(Anime(title="High Score", anilist_id=4001, api_score=9.0, studio="MAPPA"))
        db.session.add(Anime(title="Mid Score", anilist_id=4002, api_score=7.0))
        db.session.commit()

    resp = client.get("/api/recommend/for-me", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "recommendations" in body
    assert "taste_profile" in body
    assert "source" in body
    assert body["source"] == "personalized"
    assert len(body["recommendations"]) >= 1

    # Each rec has the expected shape; new signal engine yields [0, 1].
    for rec in body["recommendations"]:
        assert "anime" in rec
        assert "reason" in rec
        assert "relevance_score" in rec
        assert rec["relevance_score"] is not None
        assert 0.0 <= rec["relevance_score"] <= 1.0
