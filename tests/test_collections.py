"""Tests for /api/collections endpoints."""


def test_list_collections_empty(client, auth_headers):
    headers, _user = auth_headers
    resp = client.get("/api/collections", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json() == {"collections": []}


def test_list_collections_requires_auth(client):
    resp = client.get("/api/collections")
    assert resp.status_code == 401


def test_create_collection(client, auth_headers):
    headers, _user = auth_headers
    resp = client.post(
        "/api/collections",
        headers=headers,
        json={"name": "Cozy", "color": "amber", "icon": "flame", "description": "warm picks"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["collection"]["name"] == "Cozy"
    assert body["collection"]["color"] == "amber"
    assert body["collection"]["icon"] == "flame"
    assert body["collection"]["items_count"] == 0


def test_create_collection_requires_name(client, auth_headers):
    headers, _user = auth_headers
    resp = client.post("/api/collections", headers=headers, json={})
    assert resp.status_code == 400


def _create(client, headers, **kwargs):
    payload = {"name": "Test"}
    payload.update(kwargs)
    r = client.post("/api/collections", headers=headers, json=payload)
    return r.get_json()["collection"]


def test_get_collection_detail(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Cozy")
    r = client.get(f"/api/collections/{c['id']}", headers=headers)
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert body["name"] == "Cozy"
    assert body["items"] == []


def test_update_collection(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Old")
    r = client.patch(
        f"/api/collections/{c['id']}",
        headers=headers,
        json={"name": "New", "color": "violet"},
    )
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert body["name"] == "New"
    assert body["color"] == "violet"


def test_delete_collection(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="GoAway")
    r = client.delete(f"/api/collections/{c['id']}", headers=headers)
    assert r.status_code == 204
    r2 = client.get(f"/api/collections/{c['id']}", headers=headers)
    assert r2.status_code == 404


def test_cannot_access_other_users_collection(app, client, auth_headers):
    from models import db, User, Collection
    headers, _owner = auth_headers
    with app.app_context():
        other = User(username="other", email="o@e.com", password_hash="pw")
        db.session.add(other)
        db.session.commit()
        c = Collection(user_id=other.id, name="Not Yours")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    r = client.get(f"/api/collections/{cid}", headers=headers)
    assert r.status_code == 404


def test_cannot_add_or_remove_items_on_other_users_collection(app, client, auth_headers):
    from flask_jwt_extended import create_access_token
    from models import db, User, Collection, Anime
    headers, _owner = auth_headers
    with app.app_context():
        other = User(username="other2", email="o2@e.com", password_hash="pw")
        db.session.add(other)
        db.session.commit()
        c = Collection(user_id=other.id, name="Private")
        db.session.add(c)
        a = Anime(
            mal_id=99, title="Other", synopsis="", year=2023, episodes=12,
            studio="X", image_url="", source="ORIGINAL", status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        cid, aid = c.id, a.id

    r_post = client.post(
        f"/api/collections/{cid}/items",
        headers=headers,
        json={"anime_id": aid},
    )
    assert r_post.status_code == 404

    r_delete = client.delete(
        f"/api/collections/{cid}/items/{aid}",
        headers=headers,
    )
    assert r_delete.status_code == 404


def _make_anime(app, title="Frieren"):
    from models import db, Anime
    with app.app_context():
        a = Anime(
            mal_id=42, title=title, synopsis="", year=2023, episodes=28,
            studio="Madhouse", image_url="", source="ORIGINAL",
            status="FINISHED",
        )
        db.session.add(a)
        db.session.commit()
        return a.id


def test_add_anime_to_collection(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Picks")
    aid = _make_anime(app)

    r = client.post(
        f"/api/collections/{c['id']}/items",
        headers=headers,
        json={"anime_id": aid, "note": "must rewatch"},
    )
    assert r.status_code == 201
    item = r.get_json()["item"]
    assert item["anime_id"] == aid
    assert item["note"] == "must rewatch"


def test_adding_duplicate_anime_is_idempotent(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Picks")
    aid = _make_anime(app)

    r1 = client.post(f"/api/collections/{c['id']}/items", headers=headers, json={"anime_id": aid})
    r2 = client.post(f"/api/collections/{c['id']}/items", headers=headers, json={"anime_id": aid})
    assert r1.status_code == 201
    assert r2.status_code == 200  # already exists


def test_remove_anime_from_collection(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Picks")
    aid = _make_anime(app)
    client.post(f"/api/collections/{c['id']}/items", headers=headers, json={"anime_id": aid})

    r = client.delete(f"/api/collections/{c['id']}/items/{aid}", headers=headers)
    assert r.status_code == 204


def test_toggle_public_generates_share_token(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Share Me")
    r = client.patch(f"/api/collections/{c['id']}", headers=headers, json={"is_public": True})
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert body["is_public"] is True
    assert body["share_token"]


def test_public_endpoint_returns_collection_without_auth(client, auth_headers, app):
    headers, _ = auth_headers
    c = _create(client, headers, name="Share Me")
    patched = client.patch(f"/api/collections/{c['id']}", headers=headers, json={"is_public": True})
    token = patched.get_json()["collection"]["share_token"]

    r = client.get(f"/api/collections/public/{token}")
    assert r.status_code == 200
    assert r.get_json()["collection"]["name"] == "Share Me"


def test_public_endpoint_404_when_private(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Private")
    r = client.get(f"/api/collections/public/never-generated")
    assert r.status_code == 404


def test_public_endpoint_404_after_toggling_private(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Share Me")
    patched = client.patch(
        f"/api/collections/{c['id']}", headers=headers, json={"is_public": True}
    )
    token = patched.get_json()["collection"]["share_token"]
    # Turning public off revokes the share link.
    client.patch(
        f"/api/collections/{c['id']}", headers=headers, json={"is_public": False}
    )
    r = client.get(f"/api/collections/public/{token}")
    assert r.status_code == 404


def test_public_endpoint_omits_owner_identifiers(client, auth_headers):
    headers, _ = auth_headers
    c = _create(client, headers, name="Share Me")
    patched = client.patch(
        f"/api/collections/{c['id']}", headers=headers, json={"is_public": True}
    )
    token = patched.get_json()["collection"]["share_token"]
    r = client.get(f"/api/collections/public/{token}")
    assert r.status_code == 200
    body = r.get_json()["collection"]
    assert "user_id" not in body
    assert "share_token" not in body
