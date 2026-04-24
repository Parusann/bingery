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


def test_activity_feed_empty_user(client, auth_headers):
    """A user with no actions gets an empty list, not an error."""
    headers, _ = auth_headers
    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"items": []}


def test_activity_feed_does_not_leak_other_users(app, client, auth_headers):
    """Another user's actions must not appear in this user's feed."""
    from flask_bcrypt import Bcrypt
    from models import db, User, Anime, Rating, FanGenreVote, WatchlistEntry
    headers, _owner = auth_headers

    with app.app_context():
        bcrypt = Bcrypt(app)
        other = User(
            username="stranger",
            email="stranger-activity@example.com",
            password_hash=bcrypt.generate_password_hash("pw").decode("utf-8"),
        )
        db.session.add(other)
        db.session.commit()
        a = Anime(
            mal_id=2, title="Theirs", synopsis="", year=2021,
            episodes=12, studio="X", image_url="",
            source="ORIGINAL", status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        db.session.add_all([
            Rating(user_id=other.id, anime_id=a.id, score=7),
            FanGenreVote(user_id=other.id, anime_id=a.id, genre_tag="Horror"),
            WatchlistEntry(user_id=other.id, anime_id=a.id, status="completed"),
        ])
        db.session.commit()

    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"items": []}


def test_activity_feed_orders_newest_first(app, client, auth_headers):
    """Events are returned newest-first by timestamp."""
    from models import db, Anime, Rating
    headers, user = auth_headers

    with app.app_context():
        old = Anime(mal_id=10, title="Old", synopsis="", year=2015,
                    episodes=12, studio="S", image_url="",
                    source="ORIGINAL", status="FINISHED")
        new = Anime(mal_id=11, title="New", synopsis="", year=2024,
                    episodes=12, studio="S", image_url="",
                    source="ORIGINAL", status="FINISHED")
        db.session.add_all([old, new])
        db.session.commit()
        r_old = Rating(user_id=user.id, anime_id=old.id, score=6,
                       created_at=datetime(2020, 1, 1, 0, 0, 0),
                       updated_at=datetime(2020, 1, 1, 0, 0, 0))
        r_new = Rating(user_id=user.id, anime_id=new.id, score=8,
                       created_at=datetime(2024, 6, 1, 0, 0, 0),
                       updated_at=datetime(2024, 6, 1, 0, 0, 0))
        db.session.add_all([r_old, r_new])
        db.session.commit()

    r = client.get("/api/activity", headers=headers)
    items = r.get_json()["items"]
    timestamps = [item["timestamp"] for item in items if item["type"] == "rating"]
    assert timestamps == sorted(timestamps, reverse=True)


def test_activity_feed_before_filter(app, client, auth_headers):
    """?before=<iso> returns only events strictly older than the cutoff."""
    from models import db, Anime, Rating
    headers, user = auth_headers

    with app.app_context():
        a = Anime(mal_id=20, title="A", synopsis="", year=2020,
                  episodes=12, studio="S", image_url="",
                  source="ORIGINAL", status="FINISHED")
        b = Anime(mal_id=21, title="B", synopsis="", year=2021,
                  episodes=12, studio="S", image_url="",
                  source="ORIGINAL", status="FINISHED")
        db.session.add_all([a, b])
        db.session.commit()
        r_a = Rating(user_id=user.id, anime_id=a.id, score=7,
                     created_at=datetime(2020, 1, 1),
                     updated_at=datetime(2020, 1, 1))
        r_b = Rating(user_id=user.id, anime_id=b.id, score=8,
                     created_at=datetime(2023, 6, 1),
                     updated_at=datetime(2023, 6, 1))
        db.session.add_all([r_a, r_b])
        db.session.commit()

    cutoff = "2022-01-01T00:00:00"
    r = client.get(f"/api/activity?before={cutoff}", headers=headers)
    assert r.status_code == 200
    items = r.get_json()["items"]
    # Only the 2020 rating is strictly older than 2022-01-01.
    ratings = [item for item in items if item["type"] == "rating"]
    assert len(ratings) == 1
    assert ratings[0]["anime_title"] == "A"


def test_activity_feed_before_rejects_invalid_timestamp(client, auth_headers):
    """Bad ?before input yields 400, not a 500 crash."""
    headers, _ = auth_headers
    r = client.get("/api/activity?before=not-a-date", headers=headers)
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_activity_feed_limit_is_clamped(client, auth_headers, app):
    """?limit is clamped into [1, 200]; bogus values fall back to default."""
    headers, user = auth_headers
    _seed_activity(app, user.id)

    # Over the max — should not error.
    r = client.get("/api/activity?limit=9999", headers=headers)
    assert r.status_code == 200
    # Zero — should clamp to at least 1.
    r = client.get("/api/activity?limit=0", headers=headers)
    assert r.status_code == 200
    # Non-integer — should fall back to default, not crash.
    r = client.get("/api/activity?limit=abc", headers=headers)
    assert r.status_code == 200


def test_on_this_day_returns_prior_year_matches(app, client, auth_headers):
    """/on-this-day returns events from prior years matching today's month+day."""
    from models import db, Anime, Rating
    from routes.activity import _naive_utc_now
    headers, user = auth_headers

    with app.app_context():
        today = _naive_utc_now()
        # Prior-year rating that matches today's month+day.
        a = Anime(mal_id=30, title="Match", synopsis="", year=2020,
                  episodes=12, studio="S", image_url="",
                  source="ORIGINAL", status="FINISHED")
        # Non-match: same user, different day.
        b = Anime(mal_id=31, title="NoMatch", synopsis="", year=2020,
                  episodes=12, studio="S", image_url="",
                  source="ORIGINAL", status="FINISHED")
        db.session.add_all([a, b])
        db.session.commit()
        prior = today.replace(year=today.year - 1, hour=12, minute=0,
                              second=0, microsecond=0)
        off = prior + timedelta(days=3)
        db.session.add_all([
            Rating(user_id=user.id, anime_id=a.id, score=8,
                   created_at=prior, updated_at=prior),
            Rating(user_id=user.id, anime_id=b.id, score=5,
                   created_at=off, updated_at=off),
        ])
        db.session.commit()

    r = client.get("/api/activity/on-this-day", headers=headers)
    assert r.status_code == 200
    items = r.get_json()["items"]
    titles = {item["anime_title"] for item in items}
    assert "Match" in titles
    assert "NoMatch" not in titles


def test_on_this_day_requires_auth(client):
    r = client.get("/api/activity/on-this-day")
    assert r.status_code == 401
