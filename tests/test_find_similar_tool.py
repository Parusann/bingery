"""Tests for the find_similar_anime chat tool executor."""
import json

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


def _catalog(app):
    seed = _mk(app, "Re:Gamma", {"Isekai": 90, "Time Loop": 85}, ["Fantasy"])
    twin = _mk(app, "Twin Gamma", {"Isekai": 80, "Time Loop": 70}, ["Fantasy"])
    _mk(app, "Far Gamma", {"Mecha": 90}, ["Sci-Fi"], source="Original")
    return seed, twin


def test_find_similar_resolves_fuzzy_and_ranks(app):
    from routes.chatbot_tools import execute_tool

    _catalog(app)
    with app.app_context():
        out = json.loads(execute_tool("find_similar_anime", {"title": "re:gamma"}))
        assert out["seed"]["title"] == "Re:Gamma"
        assert out["results"][0]["title"] == "Twin Gamma"
        assert {"id", "title", "match_score", "shared_tags"} <= set(out["results"][0])


def test_find_similar_excludes_ids(app):
    from routes.chatbot_tools import execute_tool

    _, twin = _catalog(app)
    with app.app_context():
        out = json.loads(
            execute_tool(
                "find_similar_anime", {"title": "Re:Gamma", "exclude_ids": [twin]}
            )
        )
        assert all(r["id"] != twin for r in out["results"])


def test_find_similar_unknown_title_errors(app, monkeypatch):
    from routes.chatbot_tools import execute_tool
    from utils.anilist import AniListClient

    monkeypatch.setattr(
        AniListClient, "search_anime", lambda self, q, **kw: {"anime": []}
    )
    _catalog(app)
    with app.app_context():
        out = json.loads(
            execute_tool("find_similar_anime", {"title": "Zzz Nonexistent Xyz"})
        )
        assert "error" in out


def test_find_similar_mood_tags_boost(app):
    from routes.chatbot_tools import execute_tool

    _mk(app, "Re:Delta", {"Isekai": 90}, ["Fantasy"])
    _mk(app, "Dark Delta", {"Isekai": 60, "Tragedy": 80}, ["Fantasy"])
    _mk(app, "Light Delta", {"Isekai": 75, "Comedy": 80}, ["Fantasy"])
    with app.app_context():
        base = json.loads(execute_tool("find_similar_anime", {"title": "Re:Delta"}))
        assert base["results"][0]["title"] == "Light Delta"  # higher tag overlap
        moody = json.loads(
            execute_tool(
                "find_similar_anime",
                {"title": "Re:Delta", "mood_tags": ["Tragedy"]},
            )
        )
        assert moody["results"][0]["title"] == "Dark Delta"  # boost wins


def test_find_similar_tool_registered():
    from utils.ai_tools import ALL_TOOLS, TOOL_NAMES

    assert "find_similar_anime" in TOOL_NAMES
    schema = next(t for t in ALL_TOOLS if t.name == "find_similar_anime")
    assert "title" in schema.parameters["properties"]
    assert schema.parameters["required"] == ["title"]
