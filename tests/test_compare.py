"""Tests for /api/compare."""


def _seed_compare(app, user_id):
    from models import db, Anime, Rating, FanGenreVote
    with app.app_context():
        a = Anime(mal_id=1, title="A", synopsis="", year=2020,
                  episodes=12, studio="Madhouse", image_url="",
                  source="MANGA", status="FINISHED")
        b = Anime(mal_id=2, title="B", synopsis="", year=2023,
                  episodes=24, studio="MAPPA", image_url="",
                  source="ORIGINAL", status="FINISHED")
        db.session.add_all([a, b])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user_id, anime_id=a.id, score=8, review="solid"),
            Rating(user_id=user_id, anime_id=b.id, score=9, review="great"),
            FanGenreVote(user_id=user_id, anime_id=a.id, genre_tag="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_tag="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_tag="Drama"),
        ])
        db.session.commit()
        return a.id, b.id


def test_compare_two_anime(client, auth_headers, app):
    headers, user = auth_headers
    aid, bid = _seed_compare(app, user.id)

    r = client.get(f"/api/compare?a={aid}&b={bid}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["a"]["anime"]["id"] == aid
    assert body["b"]["anime"]["id"] == bid
    assert body["a"]["user"]["score"] == 8
    assert body["b"]["user"]["score"] == 9
    assert "Fantasy" in body["shared"]["fan_genres"]
    assert body["a"]["user"]["review"] == "solid"


def test_compare_requires_two_ids(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/compare?a=1", headers=headers)
    assert r.status_code == 400


def test_compare_404_when_anime_missing(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/compare?a=9999&b=10000", headers=headers)
    assert r.status_code == 404
