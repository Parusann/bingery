"""Tests for GET /api/anime/<id>/similar."""
import pytest


@pytest.fixture(autouse=True)
def _fresh_tag_index():
    from utils import similarity

    similarity._TAG_INDEX = None
    similarity._TAG_INDEX_AT = 0.0
    yield


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Franchise lookup must never hit AniList in tests."""
    monkeypatch.setattr("utils.similarity.franchise_anilist_ids", lambda s: set())


def _mk(app, title, tags, genres, **kw):
    from models import db, Anime, Genre, Tag, AnimeTag

    with app.app_context():
        a = Anime(
            title=title,
            source=kw.get("source", "Light Novel"),
            episodes=kw.get("episodes", 25),
            year=kw.get("year", 2016),
            api_score=kw.get("api_score", 8.0),
        )
        db.session.add(a)
        db.session.flush()
        for gname in genres:
            g = Genre.query.filter_by(name=gname).first()
            if not g:
                g = Genre(name=gname)
                db.session.add(g)
                db.session.flush()
            a.official_genres.append(g)
        for name, rank in tags.items():
            t = Tag.query.filter_by(name=name).first()
            if not t:
                t = Tag(name=name)
                db.session.add(t)
                db.session.flush()
            db.session.add(AnimeTag(anime_id=a.id, tag_id=t.id, rank=rank))
        db.session.commit()
        return a.id


def _catalog(app):
    seed = _mk(app, "Seed Show", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    _mk(app, "Twin Show", {"Isekai": 80, "Time Loop": 70}, ["Fantasy"])
    _mk(app, "Cousin Show", {"Isekai": 55}, ["Fantasy"])
    _mk(app, "Stranger Show", {"Mecha": 90}, ["Sci-Fi"], source="Original")
    return seed


def test_similar_returns_ranked_shape(client, app):
    seed_id = _catalog(app)
    r = client.get(f"/api/anime/{seed_id}/similar")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["seed"]["id"] == seed_id
    scores = [c["match_score"] for c in body["similar"]]
    assert scores == sorted(scores, reverse=True)
    assert body["similar"][0]["title"] == "Twin Show"
    assert "shared_tags" in body["similar"][0]
    assert "franchise" in body


def test_similar_404_on_unknown(client):
    assert client.get("/api/anime/999999/similar").status_code == 404


def test_similar_limit_respected_and_clamped(client, app):
    seed_id = _catalog(app)
    assert len(client.get(f"/api/anime/{seed_id}/similar?limit=2").get_json()["similar"]) == 2
    r = client.get(f"/api/anime/{seed_id}/similar?limit=999")
    assert r.status_code == 200
    assert len(r.get_json()["similar"]) <= 24


def test_similar_personalizes_when_authed(client, app):
    from flask_jwt_extended import create_access_token

    from models import db, Anime, Rating, User

    seed_id = _catalog(app)
    with app.app_context():
        twin = Anime.query.filter_by(title="Twin Show").one()
        u = User(username="simfan2", email="simfan2@example.com", password_hash="x")
        db.session.add(u)
        db.session.flush()
        db.session.add(Rating(user_id=u.id, anime_id=twin.id, score=9))
        db.session.commit()
        token = create_access_token(identity=str(u.id))

    r = client.get(
        f"/api/anime/{seed_id}/similar",
        headers={"Authorization": f"Bearer {token}"},
    )
    titles = [c["title"] for c in r.get_json()["similar"]]
    assert "Twin Show" not in titles  # rated => excluded for this user
