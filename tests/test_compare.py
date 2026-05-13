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


# ───────────────────────────────────────────────────────────────────────────
# /api/compare/users — taste overlap between two users
# ───────────────────────────────────────────────────────────────────────────


def _make_user(app, username, email=None, password="password", display_name=None):
    """Create a fresh user, return (headers_dict, user)."""
    from flask_jwt_extended import create_access_token
    from flask_bcrypt import Bcrypt
    from models import db, User

    bcrypt = Bcrypt(app)
    user = User(
        username=username,
        email=email or f"{username}@example.com",
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        display_name=display_name,
    )
    db.session.add(user)
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}, user


def _make_anime(app, mal_id, title):
    from models import db, Anime
    a = Anime(mal_id=mal_id, title=title, synopsis="", year=2020,
              episodes=12, studio="Studio", image_url="",
              source="MANGA", status="FINISHED")
    db.session.add(a)
    db.session.commit()
    return a


def test_compare_users_requires_auth(client):
    r = client.get("/api/compare/users?user_a=x&user_b=y")
    assert r.status_code == 401


def test_compare_users_missing_params(client, auth_headers):
    headers, _ = auth_headers
    r = client.get("/api/compare/users?user_b=tester", headers=headers)
    assert r.status_code == 400
    assert "user_a" in r.get_json()["error"]

    r = client.get("/api/compare/users?user_a=tester", headers=headers)
    assert r.status_code == 400


def test_compare_users_user_not_found(client, auth_headers):
    headers, _ = auth_headers
    r = client.get(
        "/api/compare/users?user_a=tester&user_b=does_not_exist",
        headers=headers,
    )
    assert r.status_code == 404
    assert r.get_json()["error"] == "user not found"

    r = client.get(
        "/api/compare/users?user_a=ghost&user_b=tester",
        headers=headers,
    )
    assert r.status_code == 404


def test_compare_users_basic_shape(client, auth_headers, app):
    from models import db, Rating, FanGenreVote
    headers, user_a = auth_headers
    _, user_b = _make_user(app, "alice")

    with app.app_context():
        anime = _make_anime(app, 100, "Shared Show")
        db.session.add_all([
            Rating(user_id=user_a.id, anime_id=anime.id, score=8),
            Rating(user_id=user_b.id, anime_id=anime.id, score=7),
            FanGenreVote(user_id=user_a.id, anime_id=anime.id, genre_tag="Action"),
            FanGenreVote(user_id=user_b.id, anime_id=anime.id, genre_tag="Action"),
            FanGenreVote(user_id=user_a.id, anime_id=anime.id, genre_tag="Drama"),
        ])
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_b.username}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.get_json()

    assert body["user_a"]["username"] == user_a.username
    assert body["user_a"]["id"] == user_a.id
    assert "display_name" in body["user_a"]
    assert body["user_b"]["username"] == user_b.username

    taste = body["taste"]
    assert isinstance(taste["shared_genres"], list)
    assert isinstance(taste["only_a_genres"], list)
    assert isinstance(taste["only_b_genres"], list)
    assert isinstance(taste["shared_anime"], list)
    assert isinstance(taste["score_agreement"], float)


def test_compare_users_shared_genres_sorted_and_capped(client, auth_headers, app):
    from models import db, FanGenreVote
    headers, user_a = auth_headers
    _, user_b = _make_user(app, "bob")

    # 10 shared genres. Give each a distinct combined count so ordering is
    # unambiguous: A votes (i+1) times, B votes once → combined = i+2.
    with app.app_context():
        for i in range(10):
            anime = _make_anime(app, 200 + i, f"Show{i}")
            # User A votes the genre on the anime once.
            db.session.add(FanGenreVote(
                user_id=user_a.id, anime_id=anime.id, genre_tag=f"G{i:02d}",
            ))
            # User B votes the genre on the anime once (and possibly multiple
            # anime to bump count). We just want each genre to appear in both
            # users' vote sets.
            db.session.add(FanGenreVote(
                user_id=user_b.id, anime_id=anime.id, genre_tag=f"G{i:02d}",
            ))
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_b.username}",
        headers=headers,
    )
    assert r.status_code == 200
    shared = r.get_json()["taste"]["shared_genres"]
    assert len(shared) == 8  # capped at 8
    # All counts equal here (1+1=2), so alpha tiebreak applies.
    names = [g["genre"] for g in shared]
    assert names == sorted(names)
    for entry in shared:
        assert entry["count"] == 2


def test_compare_users_only_a_genres_excludes_b(client, auth_headers, app):
    from models import db, FanGenreVote
    headers, user_a = auth_headers
    _, user_b = _make_user(app, "carol")

    with app.app_context():
        anime = _make_anime(app, 300, "OneShow")
        db.session.add_all([
            FanGenreVote(user_id=user_a.id, anime_id=anime.id, genre_tag="X"),
            FanGenreVote(user_id=user_a.id, anime_id=anime.id, genre_tag="Y"),
            FanGenreVote(user_id=user_b.id, anime_id=anime.id, genre_tag="Y"),
        ])
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_b.username}",
        headers=headers,
    )
    body = r.get_json()
    only_a = [g["genre"] for g in body["taste"]["only_a_genres"]]
    shared = [g["genre"] for g in body["taste"]["shared_genres"]]
    only_b = [g["genre"] for g in body["taste"]["only_b_genres"]]

    assert "X" in only_a
    assert "Y" not in only_a
    assert "Y" in shared
    assert "X" not in only_b
    assert "Y" not in only_b


def test_compare_users_score_agreement_formula(client, auth_headers, app):
    from models import db, Rating
    headers, user_a = auth_headers
    _, user_b = _make_user(app, "dave")

    with app.app_context():
        anime = _make_anime(app, 400, "AgreeShow")
        db.session.add_all([
            Rating(user_id=user_a.id, anime_id=anime.id, score=5),
            Rating(user_id=user_b.id, anime_id=anime.id, score=7),
        ])
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_b.username}",
        headers=headers,
    )
    # diff=2, agreement = 1 - 2/9 = 0.777..., rounded → 0.78
    assert r.get_json()["taste"]["score_agreement"] == 0.78

    # Now: max disagreement → 0.0
    _, user_c = _make_user(app, "evan")
    with app.app_context():
        anime2 = _make_anime(app, 401, "DisagreeShow")
        db.session.add_all([
            Rating(user_id=user_a.id, anime_id=anime2.id, score=10),
            Rating(user_id=user_c.id, anime_id=anime2.id, score=1),
        ])
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_c.username}",
        headers=headers,
    )
    assert r.get_json()["taste"]["score_agreement"] == 0.0

    # Identical scores → 1.0
    _, user_d = _make_user(app, "frank")
    with app.app_context():
        anime3 = _make_anime(app, 402, "TieShow")
        db.session.add_all([
            Rating(user_id=user_a.id, anime_id=anime3.id, score=5),
            Rating(user_id=user_d.id, anime_id=anime3.id, score=5),
        ])
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_d.username}",
        headers=headers,
    )
    assert r.get_json()["taste"]["score_agreement"] == 1.0


def test_compare_users_score_agreement_zero_when_no_shared_anime(client, auth_headers, app):
    from models import db, Rating
    headers, user_a = auth_headers
    _, user_b = _make_user(app, "gina")

    with app.app_context():
        a1 = _make_anime(app, 500, "OnlyA")
        a2 = _make_anime(app, 501, "OnlyB")
        db.session.add_all([
            Rating(user_id=user_a.id, anime_id=a1.id, score=8),
            Rating(user_id=user_b.id, anime_id=a2.id, score=8),
        ])
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_b.username}",
        headers=headers,
    )
    body = r.get_json()
    assert body["taste"]["score_agreement"] == 0.0
    assert body["taste"]["shared_anime"] == []


def test_compare_users_same_user_returns_perfect_agreement(client, auth_headers, app):
    from models import db, Rating
    headers, user_a = auth_headers

    with app.app_context():
        anime = _make_anime(app, 600, "Self")
        db.session.add(Rating(user_id=user_a.id, anime_id=anime.id, score=4))
        db.session.commit()

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_a.username}",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.get_json()["taste"]["score_agreement"] == 1.0


def test_compare_users_shared_anime_returns_summaries(client, auth_headers, app):
    from models import db, Rating
    headers, user_a = auth_headers
    _, user_b = _make_user(app, "henry")

    with app.app_context():
        anime = _make_anime(app, 700, "SummaryShow")
        db.session.add_all([
            Rating(user_id=user_a.id, anime_id=anime.id, score=6),
            Rating(user_id=user_b.id, anime_id=anime.id, score=6),
        ])
        db.session.commit()
        expected_id = anime.id

    r = client.get(
        f"/api/compare/users?user_a={user_a.username}&user_b={user_b.username}",
        headers=headers,
    )
    body = r.get_json()
    summaries = body["taste"]["shared_anime"]
    assert len(summaries) == 1
    item = summaries[0]
    # Matches Anime.to_dict(include_community=False) — same shape seasonal uses.
    assert item["id"] == expected_id
    assert item["title"] == "SummaryShow"
    assert "image_url" in item
    assert "official_genres" in item
    # community fields should NOT be present (compact form).
    assert "community_score" not in item
    assert "fan_genres" not in item
