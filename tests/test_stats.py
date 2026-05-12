"""Tests for /api/stats endpoints."""


def _seed_ratings(app, user_id):
    from models import db, Anime, Rating, FanGenreVote, WatchlistEntry
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
            # Watchlist drives estimated_hours_watched.
            WatchlistEntry(user_id=user_id, anime_id=a.id, status="completed"),
            WatchlistEntry(user_id=user_id, anime_id=b.id, status="completed"),
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


def test_stats_hours_watched_is_watchlist_driven(app, client, auth_headers):
    """estimated_hours_watched reflects watchlist status, not ratings.

    - Ratings alone must not contribute hours.
    - `watching` with episodes_watched counts those episodes only.
    - `completed` counts full episode count.
    - `plan_to_watch` contributes zero.
    """
    from models import db, Anime, Rating, WatchlistEntry
    headers, user = auth_headers

    with app.app_context():
        rated_only = Anime(mal_id=801, title="RatedOnly", synopsis="", year=2020,
                           episodes=12, studio="S", image_url="",
                           source="ORIGINAL", status="FINISHED")
        watching = Anime(mal_id=802, title="Watching", synopsis="", year=2021,
                         episodes=24, studio="S", image_url="",
                         source="ORIGINAL", status="FINISHED")
        done = Anime(mal_id=803, title="Done", synopsis="", year=2022,
                     episodes=12, studio="S", image_url="",
                     source="ORIGINAL", status="FINISHED")
        planned = Anime(mal_id=804, title="Planned", synopsis="", year=2023,
                        episodes=12, studio="S", image_url="",
                        source="ORIGINAL", status="FINISHED")
        db.session.add_all([rated_only, watching, done, planned])
        db.session.commit()
        db.session.add_all([
            # Rated but NOT on watchlist — must not add hours.
            Rating(user_id=user.id, anime_id=rated_only.id, score=7),
            WatchlistEntry(user_id=user.id, anime_id=watching.id,
                           status="watching", episodes_watched=6),
            WatchlistEntry(user_id=user.id, anime_id=done.id,
                           status="completed"),
            WatchlistEntry(user_id=user.id, anime_id=planned.id,
                           status="plan_to_watch"),
        ])
        db.session.commit()

    r = client.get("/api/stats", headers=headers)
    body = r.get_json()
    # watching: 6 eps * 24min = 144
    # completed: 12 eps * 24min * 1.0 = 288
    # plan_to_watch: 0
    # rated-only: 0 (no watchlist entry)
    # total = 432 min = 7.2 hours
    assert body["estimated_hours_watched"] == 7.2


def test_stats_genres_breakdown(client, auth_headers, app):
    headers, user = auth_headers
    _seed_ratings(app, user.id)
    r = client.get("/api/stats/genres", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    fantasy = next(g for g in body["genres"] if g["name"] == "Fantasy")
    assert fantasy["count"] == 2
    assert fantasy["weighted_score"] > 0


def test_stats_timeline(client, auth_headers, app):
    headers, user = auth_headers
    _seed_ratings(app, user.id)
    r = client.get("/api/stats/timeline", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert {row["year"] for row in body["timeline"]} == {2020, 2023}
    for row in body["timeline"]:
        assert "count" in row
        assert "average_score" in row


def test_stats_genres_and_timeline_require_auth(client):
    assert client.get("/api/stats/genres").status_code == 401
    assert client.get("/api/stats/timeline").status_code == 401


def test_stats_genres_empty_user(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/stats/genres", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"genres": []}


def test_stats_timeline_empty_user(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/stats/timeline", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"timeline": []}


def test_stats_timeline_is_sorted_ascending_and_skips_null_years(app, client, auth_headers):
    """Timeline must be year-ascending and must exclude anime with no year."""
    from models import db, Anime, Rating
    headers, user = auth_headers

    with app.app_context():
        early = Anime(mal_id=101, title="Early", synopsis="", year=2005,
                      episodes=12, studio="S1", image_url="",
                      source="ORIGINAL", status="FINISHED")
        mid = Anime(mal_id=102, title="Mid", synopsis="", year=2015,
                    episodes=12, studio="S2", image_url="",
                    source="ORIGINAL", status="FINISHED")
        late = Anime(mal_id=103, title="Late", synopsis="", year=2024,
                     episodes=12, studio="S3", image_url="",
                     source="ORIGINAL", status="FINISHED")
        yearless = Anime(mal_id=104, title="Yearless", synopsis="", year=None,
                         episodes=12, studio="S4", image_url="",
                         source="ORIGINAL", status="FINISHED")
        db.session.add_all([early, mid, late, yearless])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user.id, anime_id=early.id, score=6),
            Rating(user_id=user.id, anime_id=mid.id, score=7),
            Rating(user_id=user.id, anime_id=late.id, score=8),
            Rating(user_id=user.id, anime_id=yearless.id, score=9),
        ])
        db.session.commit()

    r = client.get("/api/stats/timeline", headers=headers)
    body = r.get_json()
    years = [row["year"] for row in body["timeline"]]
    assert years == [2005, 2015, 2024]  # sorted asc, yearless excluded


def test_stats_genres_does_not_leak_other_users(app, client, auth_headers):
    """Another user's votes must not appear in this user's /genres response."""
    from flask_bcrypt import Bcrypt
    from models import db, User, Anime, Rating, FanGenreVote
    headers, _owner = auth_headers

    with app.app_context():
        bcrypt = Bcrypt(app)
        other = User(
            username="strangergenres",
            email="sg@example.com",
            password_hash=bcrypt.generate_password_hash("pw").decode("utf-8"),
        )
        db.session.add(other)
        db.session.commit()
        a = Anime(mal_id=555, title="TheirsG", synopsis="", year=2010,
                  episodes=12, studio="X", image_url="",
                  source="ORIGINAL", status="FINISHED")
        db.session.add(a)
        db.session.commit()
        db.session.add_all([
            Rating(user_id=other.id, anime_id=a.id, score=10),
            FanGenreVote(user_id=other.id, anime_id=a.id, genre_tag="Horror"),
        ])
        db.session.commit()

    r = client.get("/api/stats/genres", headers=headers)
    assert r.status_code == 200
    assert r.get_json() == {"genres": []}


def test_stats_genres_mixed_rated_and_unrated_votes(app, client, auth_headers):
    """Unrated votes dilute the avg to 0 instead of being ignored.

    Previously `AVG(score)` skipped NULL, so a rated(8) + unrated vote under
    one genre yielded avg=8 and weighted=16. Now unrated contributes 0 to the
    average, so avg=(8+0)/2=4 and weighted=4*2=8.
    """
    from models import db, Anime, Rating, FanGenreVote
    headers, user = auth_headers

    with app.app_context():
        rated = Anime(mal_id=701, title="Rated", synopsis="", year=2020,
                      episodes=12, studio="S", image_url="",
                      source="ORIGINAL", status="FINISHED")
        unrated = Anime(mal_id=702, title="Unrated", synopsis="", year=2021,
                        episodes=12, studio="S", image_url="",
                        source="ORIGINAL", status="FINISHED")
        db.session.add_all([rated, unrated])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user.id, anime_id=rated.id, score=8),
            FanGenreVote(user_id=user.id, anime_id=rated.id, genre_tag="Mecha"),
            FanGenreVote(user_id=user.id, anime_id=unrated.id, genre_tag="Mecha"),
        ])
        db.session.commit()

    r = client.get("/api/stats/genres", headers=headers)
    body = r.get_json()
    mecha = next(g for g in body["genres"] if g["name"] == "Mecha")
    assert mecha["count"] == 2
    assert mecha["avg_score"] == 4.0
    assert mecha["weighted_score"] == 8.0


def test_stats_genres_handles_voted_but_unrated_anime(app, client, auth_headers):
    """A genre voted on an anime the user has not rated yields avg_score=0."""
    from models import db, Anime, FanGenreVote
    headers, user = auth_headers

    with app.app_context():
        a = Anime(mal_id=606, title="Unrated", synopsis="", year=2022,
                  episodes=12, studio="Y", image_url="",
                  source="ORIGINAL", status="FINISHED")
        db.session.add(a)
        db.session.commit()
        db.session.add(FanGenreVote(user_id=user.id, anime_id=a.id, genre_tag="Slice"))
        db.session.commit()

    r = client.get("/api/stats/genres", headers=headers)
    body = r.get_json()
    slice_entry = next(g for g in body["genres"] if g["name"] == "Slice")
    assert slice_entry["count"] == 1
    assert slice_entry["avg_score"] == 0.0
    assert slice_entry["weighted_score"] == 0.0
