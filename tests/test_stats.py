"""Tests for /api/stats endpoints."""


def _seed_ratings(app, user_id):
    from models import db, Anime, Rating, FanGenreVote
    with app.app_context():
        a = Anime(mal_id=1, title="A", synopsis="", year=2020,
                  episodes=12, studio="Madhouse", image_url="",
                  source="ORIGINAL", status="FINISHED")
        b = Anime(mal_id=2, title="B", synopsis="", year=2023,
                  episodes=24, studio="MAPPA", image_url="",
                  source="MANGA", status="FINISHED")
        db.session.add_all([a, b])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user_id, anime_id=a.id, score=8),
            Rating(user_id=user_id, anime_id=b.id, score=9),
            FanGenreVote(user_id=user_id, anime_id=a.id, genre_tag="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_tag="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_tag="Drama"),
        ])
        db.session.commit()


def test_stats_returns_aggregate_dashboard(client, auth_headers, app):
    headers, user = auth_headers
    _seed_ratings(app, user.id)

    r = client.get("/api/stats", headers=headers)
    assert r.status_code == 200
    body = r.get_json()

    assert body["totals"]["rated"] == 2
    assert body["totals"]["genre_votes"] == 3
    assert body["totals"]["average_score"] == 8.5

    assert {s["studio"] for s in body["top_studios"]} == {"Madhouse", "MAPPA"}
    assert body["estimated_hours_watched"] > 0

    years = {y["year"]: y["count"] for y in body["year_distribution"]}
    assert years == {2020: 1, 2023: 1}


def test_stats_requires_auth(client):
    r = client.get("/api/stats")
    assert r.status_code == 401
