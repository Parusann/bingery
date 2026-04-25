"""Tests for /api/seasonal endpoints."""


def _seed_seasonal(app):
    from models import db, Anime
    with app.app_context():
        a = Anime(mal_id=101, title="Winter 2026 A", synopsis="", year=2026,
                  season="WINTER", episodes=12, studio="Studio", image_url="",
                  source="ORIGINAL", status="RELEASING")
        b = Anime(mal_id=102, title="Spring 2026 B", synopsis="", year=2026,
                  season="SPRING", episodes=12, studio="Studio", image_url="",
                  source="ORIGINAL", status="NOT_YET_RELEASED")
        db.session.add_all([a, b])
        db.session.commit()


def test_seasonal_returns_filtered_by_season_year(client, auth_headers, app):
    headers, _ = auth_headers
    _seed_seasonal(app)
    r = client.get("/api/seasonal?season=WINTER&year=2026", headers=headers)
    assert r.status_code == 200
    titles = {a["title"] for a in r.get_json()["anime"]}
    assert titles == {"Winter 2026 A"}


def test_seasonal_airing_now(client, auth_headers, app):
    headers, _ = auth_headers
    _seed_seasonal(app)
    r = client.get("/api/seasonal/airing-now", headers=headers)
    assert r.status_code == 200
    titles = {a["title"] for a in r.get_json()["anime"]}
    assert titles == {"Winter 2026 A"}


def test_seasonal_rejects_bad_season(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/seasonal?season=SUMMERTIME&year=2026", headers=headers)
    assert r.status_code == 400
