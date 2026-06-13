"""Tests for /api/search — NSFW policy + param hygiene."""
from models import db, Anime, Genre


def _genre(name):
    g = db.session.query(Genre).filter_by(name=name).first()
    if not g:
        g = Genre(name=name, category="standard")
        db.session.add(g)
        db.session.flush()
    return g


def _seed(app):
    with app.app_context():
        safe = Anime(title="Steins;Gate", anilist_id=11001, api_score=9.0)
        safe2 = Anime(title="Steins;Zero", anilist_id=11004, api_score=8.8)
        hentai = Anime(title="Steins;Hidden", anilist_id=11002, api_score=9.5)
        ecchi = Anime(title="Steins;Cheeky", anilist_id=11003, api_score=8.5)
        hentai.official_genres.append(_genre("Hentai"))
        ecchi.official_genres.append(_genre("Ecchi"))
        db.session.add_all([safe, safe2, hentai, ecchi])
        db.session.commit()


def test_autocomplete_applies_nsfw_policy(client, app):
    _seed(app)
    r = client.get("/api/search/autocomplete?q=stein")
    titles = [x["title"] for x in r.get_json()["results"]]
    assert "Steins;Gate" in titles
    assert "Steins;Hidden" not in titles  # hard-blocked, always
    assert "Steins;Cheeky" not in titles  # soft-blocked by default


def test_autocomplete_opt_in_reveals_soft_blocked_only(client, app):
    _seed(app)
    r = client.get("/api/search/autocomplete?q=stein&include_nsfw=true")
    titles = [x["title"] for x in r.get_json()["results"]]
    assert "Steins;Cheeky" in titles
    assert "Steins;Hidden" not in titles  # hard block survives opt-in


def test_full_search_applies_nsfw_policy_even_with_opt_in(client, app):
    _seed(app)
    r = client.get("/api/search/full?q=stein&include_nsfw=true")
    titles = [x["title"] for x in r.get_json()["results"]]
    assert "Steins;Gate" in titles
    assert "Steins;Cheeky" in titles
    assert "Steins;Hidden" not in titles


def test_autocomplete_negative_limit_clamped(client, app):
    _seed(app)
    r = client.get("/api/search/autocomplete?q=stein&limit=-3")
    assert r.status_code == 200
    # Negative limits must clamp to at least 1 row, never "no limit".
    assert len(r.get_json()["results"]) == 1
