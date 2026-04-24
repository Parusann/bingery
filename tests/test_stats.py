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


def test_stats_empty_user_returns_zeroes(client, auth_headers):
    """User with no ratings gets zero totals, empty distributions, no divide-by-zero."""
    headers, _ = auth_headers
    r = client.get("/api/stats", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["totals"]["rated"] == 0
    assert body["totals"]["genre_votes"] == 0
    assert body["totals"]["average_score"] == 0.0
    assert body["year_distribution"] == []
    assert body["top_studios"] == []
    assert body["top_fan_tags"] == []
    assert body["estimated_hours_watched"] == 0.0
    # Score distribution is always the 1..10 skeleton, zero-filled.
    assert len(body["score_distribution"]) == 10
    assert all(bucket["count"] == 0 for bucket in body["score_distribution"])


def test_stats_score_distribution_has_all_ten_buckets(client, auth_headers, app):
    """score_distribution covers 1..10 even when only some scores appear."""
    headers, user = auth_headers
    _seed_ratings(app, user.id)
    r = client.get("/api/stats", headers=headers)
    body = r.get_json()
    scores = {b["score"]: b["count"] for b in body["score_distribution"]}
    assert set(scores.keys()) == set(range(1, 11))
    # Seeded ratings are 8 and 9.
    assert scores[8] == 1
    assert scores[9] == 1
    assert scores[1] == 0
    assert scores[7] == 0


def test_stats_top_fan_tags_reflects_votes(client, auth_headers, app):
    """top_fan_tags aggregates genre_tag counts for the current user."""
    headers, user = auth_headers
    _seed_ratings(app, user.id)
    r = client.get("/api/stats", headers=headers)
    body = r.get_json()
    tags = {t["name"]: t["count"] for t in body["top_fan_tags"]}
    # Seeded: Fantasy x2, Drama x1.
    assert tags == {"Fantasy": 2, "Drama": 1}


def test_stats_does_not_leak_other_users_data(app, client, auth_headers):
    """Ratings / votes belonging to another user must not appear in this user's stats."""
    from flask_bcrypt import Bcrypt
    from models import db, User, Anime, Rating, FanGenreVote
    headers, _owner = auth_headers

    with app.app_context():
        bcrypt = Bcrypt(app)
        other = User(
            username="stranger",
            email="stranger@example.com",
            password_hash=bcrypt.generate_password_hash("pw").decode("utf-8"),
        )
        db.session.add(other)
        db.session.commit()
        a = Anime(
            mal_id=777, title="Theirs", synopsis="", year=1999,
            episodes=100, studio="GhostStudio", image_url="",
            source="ORIGINAL", status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        db.session.add_all([
            Rating(user_id=other.id, anime_id=a.id, score=3),
            FanGenreVote(user_id=other.id, anime_id=a.id, genre_tag="Horror"),
        ])
        db.session.commit()

    r = client.get("/api/stats", headers=headers)
    body = r.get_json()
    assert body["totals"]["rated"] == 0
    assert body["totals"]["genre_votes"] == 0
    assert body["top_studios"] == []
    assert body["top_fan_tags"] == []
    assert body["year_distribution"] == []
