"""Tests for /api/anime routes — param hygiene."""
import pytest
from sqlalchemy import event

from models import db, Anime, FanGenreVote, Genre, Rating, User


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


def test_catalog_community_order_and_display_titles(client, app):
    user = User(username="rater", email="rater@example.com", password_hash="x")
    low = Anime(title="AAA", title_english="Zulu", api_score=10)
    high = Anime(title="ZZZ", title_english="alpha", api_score=1)
    tied = Anime(title="Beta")
    unrated = Anime(title="First by API", api_score=9)
    db.session.add_all([user, low, high, tied, unrated])
    db.session.flush()
    for anime, score in [(low, 2), (high, 9), (tied, 9)]:
        db.session.add(Rating(user_id=user.id, anime_id=anime.id, score=score))
    db.session.commit()

    def titles(query):
        return [a["title"] for a in client.get("/api/anime?" + query).get_json()["anime"]]

    assert titles("sort=community_score&per_page=2") == ["ZZZ", "Beta"]
    assert titles("sort=community_score&per_page=2&page=2") == ["AAA", "First by API"]
    assert titles("sort=community_score&order=asc") == ["AAA", "ZZZ", "Beta", "First by API"]
    assert titles("sort=title&order=asc") == ["ZZZ", "Beta", "First by API", "AAA"]
    page = client.get("/api/anime?page=-10&per_page=-3").get_json()
    assert (page["page"], page["per_page"], len(page["anime"])) == (1, 1, 1)


def test_available_catalog_genres_follow_visible_titles(client, app):
    action, ecchi, hentai, hidden, unused = [
        Genre(name=n) for n in ("Action", "Ecchi", "Hentai", "Drama", "Unused")
    ]
    db.session.add_all([
        Anime(title="Main", official_genres=[action]),
        Anime(title="Soft", official_genres=[ecchi]),
        Anime(title="Hard", official_genres=[hentai, hidden]), unused,
    ])
    db.session.commit()

    def names(query):
        return {g["name"] for g in client.get("/api/anime/genres?" + query).get_json()["all"]}

    assert names("catalog=true") == {"Action"}
    assert names("catalog=true&include_nsfw=true") == {"Action", "Ecchi"}
    assert "Unused" in names("")


@pytest.mark.parametrize(("route", "key"), [("/api/anime", "anime"), ("/api/search/full", "results")])
def test_catalog_page_batches_community_fields(client, app, route, key):
    first, second = [User(username=n, email=n + "@example.com", password_hash="x") for n in ("u1", "u2")]
    titles = [Anime(title=f"Show {n}", api_score=8) for n in range(24)]
    titles[0].official_genres.append(Genre(name="Action"))
    db.session.add_all([first, second, *titles])
    db.session.flush()
    aid = titles[0].id
    db.session.add_all([
        Rating(anime_id=aid, user_id=first.id, score=7),
        Rating(anime_id=aid, user_id=second.id, score=8),
        FanGenreVote(anime_id=aid, user_id=first.id, genre_tag="Mystery"),
        FanGenreVote(anime_id=aid, user_id=second.id, genre_tag="Mystery"),
        FanGenreVote(anime_id=aid, user_id=second.id, genre_tag="Comedy"),
    ])
    db.session.commit()
    queries = []

    def count_selects(conn, cursor, sql, params, context, executemany):
        if sql.lstrip().upper().startswith("SELECT"):
            queries.append(sql)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        data = client.get(route + "?per_page=24").get_json()[key]
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert len(data) == 24
    assert len(queries) <= 6
    rated, unrated = data[:2]
    assert rated["rating_count"] == 2 and rated["community_score"] == 7.5
    assert rated["official_genres"][0]["name"] == "Action"
    assert rated["fan_genres"] == [
        {"genre": "Mystery", "votes": 2, "percentage": 100.0},
        {"genre": "Comedy", "votes": 1, "percentage": 50.0},
    ]
    assert unrated["rating_count"] == 0 and unrated["community_score"] is None
    assert unrated["fan_genres"] == []
