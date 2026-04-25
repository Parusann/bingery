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


def _seed_seasonal_production_vocab(app):
    """Seed rows using the values utils/anilist.py actually stores in prod."""
    from models import db, Anime
    with app.app_context():
        a = Anime(mal_id=201, title="Winter 2026 Prod", synopsis="", year=2026,
                  season="winter", episodes=12, studio="Studio", image_url="",
                  source="ORIGINAL", status="Currently Airing")
        db.session.add(a)
        db.session.commit()


def _make_second_user(app, username="tester2", email="tester2@example.com"):
    from flask_jwt_extended import create_access_token
    from flask_bcrypt import Bcrypt
    from models import db, User
    bcrypt = Bcrypt(app)
    user = User(
        username=username,
        email=email,
        password_hash=bcrypt.generate_password_hash("password").decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}, user


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


def test_seasonal_matches_production_vocabulary(client, auth_headers, app):
    """Season=lowercase + status='Currently Airing' must still match."""
    headers, _ = auth_headers
    _seed_seasonal_production_vocab(app)

    r = client.get("/api/seasonal?season=WINTER&year=2026", headers=headers)
    assert r.status_code == 200
    titles = {a["title"] for a in r.get_json()["anime"]}
    assert titles == {"Winter 2026 Prod"}

    r = client.get("/api/seasonal/airing-now", headers=headers)
    assert r.status_code == 200
    titles = {a["title"] for a in r.get_json()["anime"]}
    assert titles == {"Winter 2026 Prod"}


def test_seasonal_requires_year(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/seasonal?season=WINTER", headers=headers)
    assert r.status_code == 400
    assert "year" in r.get_json()["error"].lower()


def test_seasonal_rejects_non_int_year(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/seasonal?season=WINTER&year=abc", headers=headers)
    assert r.status_code == 400
    assert "integer" in r.get_json()["error"].lower()


def test_seasonal_overlay_isolated_per_user(client, auth_headers, app):
    """User B must not see user A's watchlist overlay on shared anime."""
    from models import db, Anime, WatchlistEntry
    headers_a, user_a = auth_headers
    _seed_seasonal(app)

    with app.app_context():
        anime = db.session.query(Anime).filter_by(title="Winter 2026 A").first()
        entry = WatchlistEntry(
            user_id=user_a.id,
            anime_id=anime.id,
            status="completed",
            is_favorite=True,
        )
        db.session.add(entry)
        db.session.commit()

    # Sanity: user A sees their own overlay.
    r_a = client.get("/api/seasonal?season=WINTER&year=2026", headers=headers_a)
    assert r_a.status_code == 200
    a_payload = next(a for a in r_a.get_json()["anime"] if a["title"] == "Winter 2026 A")
    assert a_payload["user_status"] == "completed"
    assert a_payload["is_favorite"] is True

    # User B: no overlay, ever.
    headers_b, _ = _make_second_user(app)
    r_b = client.get("/api/seasonal?season=WINTER&year=2026", headers=headers_b)
    assert r_b.status_code == 200
    b_payload = next(a for a in r_b.get_json()["anime"] if a["title"] == "Winter 2026 A")
    assert b_payload["user_status"] is None
    assert b_payload["is_favorite"] is False
