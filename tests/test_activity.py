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
    assert "events" in body
    kinds = {item["kind"] for item in body["events"]}
    assert {"rating", "genre_vote", "watch_status"}.issubset(kinds)

    for item in body["events"]:
        assert "id" in item
        assert "anime" in item
        if item["kind"] != "collection_create":
            assert item["anime"] is not None
            assert "id" in item["anime"]
            assert "title" in item["anime"]
            assert "image_url" in item["anime"]
        assert "created_at" in item


def test_activity_feed_respects_limit(client, auth_headers, app):
    headers, user = auth_headers
    _seed_activity(app, user.id)
    r = client.get("/api/activity?limit=1", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert len(body["events"]) == 1
    assert body["page"] == 1
    # With 3 events and limit=1, pages should be 3.
    assert body["pages"] == 3


def test_activity_requires_auth(client):
    r = client.get("/api/activity")
    assert r.status_code == 401


def test_activity_feed_empty_user(client, auth_headers):
    """A user with no actions gets an empty events list, not an error."""
    headers, _ = auth_headers
    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["events"] == []
    assert body["page"] == 1
    assert body["pages"] == 1


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
    body = r.get_json()
    assert body["events"] == []
    assert body["page"] == 1
    assert body["pages"] == 1


def test_activity_feed_orders_newest_first(app, client, auth_headers):
    """Events are returned newest-first by created_at."""
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
    events = r.get_json()["events"]
    timestamps = [item["created_at"] for item in events if item["kind"] == "rating"]
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
    events = r.get_json()["events"]
    # Only the 2020 rating is strictly older than 2022-01-01.
    ratings = [item for item in events if item["kind"] == "rating"]
    assert len(ratings) == 1
    assert ratings[0]["anime"]["title"] == "A"


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


def test_activity_feed_page_pagination(app, client, auth_headers):
    """?page=2&limit=2 returns the second slice with correct pages count."""
    from models import db, Anime, Rating
    headers, user = auth_headers

    with app.app_context():
        animes = []
        for i in range(5):
            an = Anime(
                mal_id=100 + i, title=f"P{i}", synopsis="", year=2020,
                episodes=12, studio="S", image_url="",
                source="ORIGINAL", status="FINISHED",
            )
            db.session.add(an)
            animes.append(an)
        db.session.commit()
        # Distinct timestamps so order is deterministic; descending index = newest.
        for i, an in enumerate(animes):
            ts = datetime(2024, 1, i + 1, 0, 0, 0)
            db.session.add(
                Rating(
                    user_id=user.id, anime_id=an.id, score=5 + i,
                    created_at=ts, updated_at=ts,
                )
            )
        db.session.commit()

    r1 = client.get("/api/activity?page=1&limit=2", headers=headers)
    r2 = client.get("/api/activity?page=2&limit=2", headers=headers)
    r3 = client.get("/api/activity?page=3&limit=2", headers=headers)
    assert r1.status_code == r2.status_code == r3.status_code == 200

    b1, b2, b3 = r1.get_json(), r2.get_json(), r3.get_json()
    assert b1["page"] == 1
    assert b2["page"] == 2
    assert b3["page"] == 3
    # 5 events / 2 per page => ceil = 3 pages.
    assert b1["pages"] == b2["pages"] == b3["pages"] == 3

    assert len(b1["events"]) == 2
    assert len(b2["events"]) == 2
    assert len(b3["events"]) == 1

    # No overlap between pages.
    ids = (
        [e["id"] for e in b1["events"]]
        + [e["id"] for e in b2["events"]]
        + [e["id"] for e in b3["events"]]
    )
    assert len(ids) == len(set(ids)) == 5


def test_activity_feed_pages_minimum_one(client, auth_headers):
    """An empty feed still reports pages=1, page=1, events=[]."""
    headers, _ = auth_headers
    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body == {"events": [], "page": 1, "pages": 1}


def test_activity_feed_page_invalid_clamps_to_one(client, auth_headers, app):
    """page=abc and page=0 fall back to page 1."""
    headers, user = auth_headers
    _seed_activity(app, user.id)

    for bad in ("abc", "0", "-3"):
        r = client.get(f"/api/activity?page={bad}", headers=headers)
        assert r.status_code == 200
        assert r.get_json()["page"] == 1


def test_activity_feed_event_id_is_unique_across_kinds(app, client, auth_headers):
    """IDs synthesized for different kinds must never collide."""
    from models import (
        db, Anime, Rating, FanGenreVote, WatchlistEntry, Collection, CollectionItem,
    )
    headers, user = auth_headers

    with app.app_context():
        a = Anime(
            mal_id=300, title="Multi", synopsis="", year=2022,
            episodes=12, studio="S", image_url="",
            source="ORIGINAL", status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        # All sharing PK=1-ish across tables — collision target if IDs were
        # taken straight from the primary key.
        db.session.add(Rating(user_id=user.id, anime_id=a.id, score=8))
        db.session.add(FanGenreVote(
            user_id=user.id, anime_id=a.id, genre_tag="Test",
        ))
        db.session.add(WatchlistEntry(
            user_id=user.id, anime_id=a.id, status="completed",
            is_favorite=True,
        ))
        col = Collection(user_id=user.id, name="Faves")
        db.session.add(col)
        db.session.commit()
        db.session.add(CollectionItem(collection_id=col.id, anime_id=a.id))
        db.session.commit()

    r = client.get("/api/activity?limit=100", headers=headers)
    assert r.status_code == 200
    events = r.get_json()["events"]
    ids = [e["id"] for e in events]
    assert len(ids) == len(set(ids))
    # Sanity: we should see at least these distinct kinds.
    kinds = {e["kind"] for e in events}
    assert {
        "rating", "genre_vote", "watch_status", "favorite",
        "collection_item", "collection_create",
    }.issubset(kinds)


def test_activity_feed_emits_favorite_event_for_favorited_watchlist(
    app, client, auth_headers,
):
    """A WatchlistEntry with is_favorite=True must emit BOTH watch_status and favorite."""
    from models import db, Anime, WatchlistEntry
    headers, user = auth_headers

    with app.app_context():
        a = Anime(
            mal_id=400, title="Fav", synopsis="", year=2020,
            episodes=12, studio="S", image_url="",
            source="ORIGINAL", status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        db.session.add(WatchlistEntry(
            user_id=user.id, anime_id=a.id,
            status="watching", is_favorite=True,
        ))
        db.session.commit()

    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    events = r.get_json()["events"]
    kinds = [e["kind"] for e in events]
    assert "watch_status" in kinds
    assert "favorite" in kinds

    fav = next(e for e in events if e["kind"] == "favorite")
    assert fav["meta"] == {}
    assert fav["anime"] is not None
    assert fav["anime"]["title"] == "Fav"


def test_activity_feed_emits_collection_item_event(app, client, auth_headers):
    """Adding an anime to a collection emits a collection_item event."""
    from models import db, Anime, Collection, CollectionItem
    headers, user = auth_headers

    with app.app_context():
        a = Anime(
            mal_id=500, title="ColItem", synopsis="", year=2020,
            episodes=12, studio="S", image_url="",
            source="ORIGINAL", status="FINISHED",
        )
        db.session.add(a)
        col = Collection(user_id=user.id, name="My List")
        db.session.add_all([a, col])
        db.session.commit()
        db.session.add(CollectionItem(collection_id=col.id, anime_id=a.id))
        db.session.commit()
        col_id = col.id
        anime_id = a.id

    r = client.get("/api/activity?limit=100", headers=headers)
    assert r.status_code == 200
    events = r.get_json()["events"]
    item_events = [e for e in events if e["kind"] == "collection_item"]
    assert len(item_events) == 1
    e = item_events[0]
    assert e["anime"] is not None
    assert e["anime"]["id"] == anime_id
    assert e["meta"]["collection_id"] == col_id
    assert e["meta"]["collection_title"] == "My List"


def test_activity_feed_emits_collection_create_event(app, client, auth_headers):
    """Creating a Collection emits a collection_create event with anime=null."""
    from models import db, Collection
    headers, user = auth_headers

    with app.app_context():
        col = Collection(user_id=user.id, name="Brand New")
        db.session.add(col)
        db.session.commit()

    r = client.get("/api/activity?limit=100", headers=headers)
    assert r.status_code == 200
    events = r.get_json()["events"]
    create_events = [e for e in events if e["kind"] == "collection_create"]
    assert len(create_events) == 1
    e = create_events[0]
    assert e["anime"] is None
    assert e["meta"] == {"title": "Brand New"}


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
    # /on-this-day still uses the same event shape now (anime nested object).
    titles = {item["anime"]["title"] for item in items if item.get("anime")}
    assert "Match" in titles
    assert "NoMatch" not in titles


def test_on_this_day_requires_auth(client):
    r = client.get("/api/activity/on-this-day")
    assert r.status_code == 401


# ─── dub_report events ───────────────────────────────────────────────────────


def _seed_dub_report(app, user_id, *, status="pending", note=None):
    from datetime import timezone
    from models import Anime, DubReport, Episode, db

    with app.app_context():
        anime = Anime(
            mal_id=42,
            title="Mushishi",
            synopsis="",
            year=2005,
            episodes=26,
            studio="Artland",
            image_url="",
            source="MANGA",
            status="FINISHED",
        )
        db.session.add(anime)
        db.session.commit()
        ep = Episode(anime_id=anime.id, episode_number=7)
        db.session.add(ep)
        db.session.commit()
        report = DubReport(
            episode_id=ep.id,
            submitted_by=user_id,
            air_date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            status=status,
            note=note,
        )
        db.session.add(report)
        db.session.commit()
        return anime.id, ep.id, report.id


def test_activity_feed_includes_user_dub_reports(client, auth_headers, app):
    headers, user = auth_headers
    _seed_dub_report(app, user.id, note="seen on the official channel")
    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    events = r.get_json()["events"]
    dub_events = [e for e in events if e["kind"] == "dub_report"]
    assert len(dub_events) == 1
    ev = dub_events[0]
    assert ev["anime"]["title"] == "Mushishi"
    assert ev["meta"]["episode_number"] == 7
    assert ev["meta"]["status"] == "pending"
    assert ev["meta"]["note"] == "seen on the official channel"
    assert ev["meta"]["air_date"].startswith("2026-06-01T12:00:00")


def test_activity_feed_dub_report_isolates_to_submitter(app, client, auth_headers):
    from flask_bcrypt import Bcrypt
    from models import User, db

    headers, _owner = auth_headers
    with app.app_context():
        bcrypt = Bcrypt(app)
        stranger = User(
            username="stranger",
            email="stranger@example.com",
            password_hash=bcrypt.generate_password_hash("pw").decode("utf-8"),
        )
        db.session.add(stranger)
        db.session.commit()
        stranger_id = stranger.id

    _seed_dub_report(app, stranger_id)
    r = client.get("/api/activity", headers=headers)
    assert r.status_code == 200
    dub_events = [e for e in r.get_json()["events"] if e["kind"] == "dub_report"]
    assert dub_events == []


def test_activity_feed_dub_report_status_reflects_accepted(client, auth_headers, app):
    headers, user = auth_headers
    _seed_dub_report(app, user.id, status="accepted", note=None)
    r = client.get("/api/activity", headers=headers)
    dub_events = [e for e in r.get_json()["events"] if e["kind"] == "dub_report"]
    assert len(dub_events) == 1
    assert dub_events[0]["meta"]["status"] == "accepted"
    assert dub_events[0]["meta"]["note"] is None
