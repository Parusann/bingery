"""Tests for /api/auth endpoints, focused on the display_name field."""


def test_register_persists_display_name(client):
    """display_name is optional but, when provided, persists and echoes back."""
    r = client.post(
        "/api/auth/register",
        json={
            "username": "dn_user",
            "email": "dn@example.com",
            "password": "password123",
            "display_name": "Display Name",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["display_name"] == "Display Name"


def test_register_without_display_name_defaults_to_null(client):
    """Omitting display_name yields null in the response."""
    r = client.post(
        "/api/auth/register",
        json={
            "username": "no_dn_user",
            "email": "no_dn@example.com",
            "password": "password123",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["display_name"] is None


def test_register_strips_and_truncates_display_name(client):
    """Whitespace is stripped; display_name is capped at 80 chars."""
    long = "a" * 200
    r = client.post(
        "/api/auth/register",
        json={
            "username": "long_dn",
            "email": "long_dn@example.com",
            "password": "password123",
            "display_name": "   " + long + "   ",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["display_name"] == "a" * 80


def test_register_empty_display_name_treated_as_unset(client):
    """An empty/whitespace-only display_name is stored as null."""
    r = client.post(
        "/api/auth/register",
        json={
            "username": "empty_dn",
            "email": "empty_dn@example.com",
            "password": "password123",
            "display_name": "   ",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["display_name"] is None


def test_update_profile_can_change_display_name(client):
    """PATCH /api/auth/me updates display_name."""
    r = client.post(
        "/api/auth/register",
        json={
            "username": "patch_dn",
            "email": "patch_dn@example.com",
            "password": "password123",
        },
    )
    token = r.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r2 = client.patch(
        "/api/auth/me",
        json={"display_name": "Updated Name"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.get_json()["user"]["display_name"] == "Updated Name"

    # Clearing back to null
    r3 = client.patch(
        "/api/auth/me",
        json={"display_name": ""},
        headers=headers,
    )
    assert r3.status_code == 200
    assert r3.get_json()["user"]["display_name"] is None
