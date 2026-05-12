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
        # Third anime: no rating / no fan votes from caller — exercises
        # the empty user-data branch.
        c = Anime(mal_id=3, title="C", synopsis="", year=2021,
                  episodes=12, studio="Bones", image_url="",
                  source="MANGA", status="FINISHED")
        db.session.add_all([a, b, c])
        db.session.commit()
        db.session.add_all([
            Rating(user_id=user_id, anime_id=a.id, score=8, review="solid"),
            Rating(user_id=user_id, anime_id=b.id, score=9, review="great"),
            FanGenreVote(user_id=user_id, anime_id=a.id, genre_tag="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_tag="Fantasy"),
            FanGenreVote(user_id=user_id, anime_id=b.id, genre_tag="Drama"),
        ])
        db.session.commit()
        return a.id, b.id, c.id


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


def test_compare_two_anime(client, auth_headers, app):
    headers, user = auth_headers
    aid, bid, _cid = _seed_compare(app, user.id)

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


def test_compare_shared_studio_when_same(client, auth_headers, app):
    """Two anime with the same studio populate shared.studios."""
    from models import db, Anime
    headers, _ = auth_headers
    with app.app_context():
        a = Anime(mal_id=11, title="A11", synopsis="", year=2020,
                  episodes=12, studio="Madhouse", image_url="",
                  source="MANGA", status="FINISHED")
        b = Anime(mal_id=12, title="B12", synopsis="", year=2021,
                  episodes=12, studio="Madhouse", image_url="",
                  source="MANGA", status="FINISHED")
        db.session.add_all([a, b])
        db.session.commit()
        aid, bid = a.id, b.id

    r = client.get(f"/api/compare?a={aid}&b={bid}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    assert body["shared"]["studios"] == ["Madhouse"]


def test_compare_404_when_one_id_invalid(client, auth_headers, app):
    """If only one of {a, b} resolves, still return 404."""
    headers, user = auth_headers
    aid, _bid, _cid = _seed_compare(app, user.id)

    r = client.get(f"/api/compare?a={aid}&b=9999", headers=headers)
    assert r.status_code == 404

    r = client.get(f"/api/compare?a=9999&b={aid}", headers=headers)
    assert r.status_code == 404


def test_compare_empty_user_data_branch(client, auth_headers, app):
    """Anime with no Rating and no FanGenreVote yields None/[] for user fields."""
    headers, user = auth_headers
    aid, _bid, cid = _seed_compare(app, user.id)

    r = client.get(f"/api/compare?a={aid}&b={cid}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()
    # `a` has rating + fan votes — sanity check the seed wired correctly.
    assert body["a"]["user"]["score"] == 8
    # `c` has neither — must fall through the rating/fan-vote `None`/[] paths.
    assert body["b"]["user"]["score"] is None
    assert body["b"]["user"]["review"] is None
    assert body["b"]["user"]["fan_genres"] == []


def test_compare_user_data_isolated_per_user(client, auth_headers, app):
    """User A's rating/fan-vote on anime A must not leak when user B compares."""
    from models import db, Anime, Rating, FanGenreVote
    headers_a, _user_a = auth_headers
    aid, bid, _cid = _seed_compare(app, _user_a.id)

    # Second user gives anime A their own rating and fan vote.
    headers_b, user_b = _make_second_user(app)
    with app.app_context():
        db.session.add_all([
            Rating(user_id=user_b.id, anime_id=aid, score=3, review="meh"),
            FanGenreVote(user_id=user_b.id, anime_id=aid, genre_tag="Horror"),
        ])
        db.session.commit()

    # First user's compare must reflect only their own data on anime A,
    # not user B's score/review/fan_genres.
    r = client.get(f"/api/compare?a={aid}&b={bid}", headers=headers_a)
    assert r.status_code == 200
    body = r.get_json()
    assert body["a"]["user"]["score"] == 8
    assert body["a"]["user"]["review"] == "solid"
    assert "Horror" not in body["a"]["user"]["fan_genres"]

    # Sanity from user B's side: their data is what's returned for them,
    # and user A's is not.
    r = client.get(f"/api/compare?a={aid}&b={bid}", headers=headers_b)
    assert r.status_code == 200
    body = r.get_json()
    assert body["a"]["user"]["score"] == 3
    assert body["a"]["user"]["review"] == "meh"
    assert body["a"]["user"]["fan_genres"] == ["Horror"]
    # User B has no data on anime B.
    assert body["b"]["user"]["score"] is None
    assert body["b"]["user"]["fan_genres"] == []
