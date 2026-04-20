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
