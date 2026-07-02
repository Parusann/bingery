"""Because-you-loved row on /api/recommend/for-me."""
import pytest


@pytest.fixture(autouse=True)
def _fresh_tag_index():
    from utils import similarity

    similarity._TAG_INDEX = None
    similarity._TAG_IDF = None
    similarity._TAG_INDEX_AT = 0.0
    yield


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr("utils.similarity.franchise_anilist_ids", lambda *a, **k: set())


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


def test_because_you_loved_present_with_tagged_high_rating(client, app, auth_headers):
    from models import db, Rating

    headers, user = auth_headers
    seed_id = _mk(app, "Loved Seed", {"Isekai": 90}, ["Fantasy"])
    _mk(app, "Suggested Sib", {"Isekai": 85}, ["Fantasy"])
    with app.app_context():
        db.session.add(Rating(user_id=user.id, anime_id=seed_id, score=9))
        db.session.commit()

    r = client.get("/api/recommend/for-me", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["because_you_loved"]["seed"]["title"] == "Loved Seed"
    titles = [i["title"] for i in body["because_you_loved"]["items"]]
    assert "Suggested Sib" in titles
    assert "Loved Seed" not in titles
    assert len(body["because_you_loved"]["items"]) <= 6


def test_because_you_loved_absent_without_qualifying_seed(client, app, auth_headers):
    from models import db, Rating

    headers, user = auth_headers
    plain = _mk(app, "Untagged Show", {}, ["Fantasy"])
    with app.app_context():
        db.session.add(Rating(user_id=user.id, anime_id=plain, score=9))
        db.session.commit()

    r = client.get("/api/recommend/for-me", headers=headers)
    assert r.status_code == 200
    assert "because_you_loved" not in r.get_json()
