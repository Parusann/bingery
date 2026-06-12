"""Tests for /api/auth endpoints, focused on the display_name field."""


def _register_verified(client, sent_codes, payload):
    """Two-step sign-up: register (202) then verify with the emailed code.
    Returns the verify response (201 {token, user})."""
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 202, r.get_json()
    _, code = sent_codes[-1]
    rv = client.post(
        "/api/auth/verify",
        json={"email": payload["email"], "code": code},
    )
    assert rv.status_code == 201, rv.get_json()
    return rv


def test_register_persists_display_name(client, sent_codes):
    """display_name is optional but, when provided, persists and echoes back."""
    r = _register_verified(client, sent_codes, {
        "username": "dn_user",
        "email": "dn@example.com",
        "password": "password123",
        "display_name": "Display Name",
    })
    body = r.get_json()
    assert body["user"]["display_name"] == "Display Name"


def test_register_without_display_name_defaults_to_null(client, sent_codes):
    """Omitting display_name yields null in the response."""
    r = _register_verified(client, sent_codes, {
        "username": "no_dn_user",
        "email": "no_dn@example.com",
        "password": "password123",
    })
    body = r.get_json()
    assert body["user"]["display_name"] is None


def test_register_strips_and_truncates_display_name(client, sent_codes):
    """Whitespace is stripped; display_name is capped at 80 chars."""
    long = "a" * 200
    r = _register_verified(client, sent_codes, {
        "username": "long_dn",
        "email": "long_dn@example.com",
        "password": "password123",
        "display_name": "   " + long + "   ",
    })
    body = r.get_json()
    assert body["user"]["display_name"] == "a" * 80


def test_register_empty_display_name_treated_as_unset(client, sent_codes):
    """An empty/whitespace-only display_name is stored as null."""
    r = _register_verified(client, sent_codes, {
        "username": "empty_dn",
        "email": "empty_dn@example.com",
        "password": "password123",
        "display_name": "   ",
    })
    body = r.get_json()
    assert body["user"]["display_name"] is None


def test_update_profile_can_change_display_name(client, sent_codes):
    """PATCH /api/auth/me updates display_name."""
    r = _register_verified(client, sent_codes, {
        "username": "patch_dn",
        "email": "patch_dn@example.com",
        "password": "password123",
    })
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


def test_login_unknown_email_burns_dummy_bcrypt_check(client, monkeypatch):
    """Anti-enumeration: unknown emails must cost one bcrypt check like the
    wrong-password path, so login timing does not reveal registered emails."""
    import routes.auth as auth_module

    calls = []
    real = auth_module.bcrypt.check_password_hash
    monkeypatch.setattr(
        auth_module.bcrypt,
        "check_password_hash",
        lambda pw_hash, pw: (calls.append(pw_hash), real(pw_hash, pw))[1],
    )
    r = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "pw123456"},
    )
    assert r.status_code == 401
    assert r.get_json() == {"error": "Invalid email or password."}
    assert len(calls) == 1


def test_patch_me_rejects_non_string_fields(client, auth_headers):
    headers, _user = auth_headers
    assert client.patch("/api/auth/me", json={"username": 123}, headers=headers).status_code == 400
    assert client.patch("/api/auth/me", json={"bio": 123}, headers=headers).status_code == 400
    assert client.patch("/api/auth/me", json={"avatar_url": 123}, headers=headers).status_code == 400


def test_patch_me_rejects_overlong_username(client, auth_headers):
    headers, _user = auth_headers
    r = client.patch("/api/auth/me", json={"username": "x" * 81}, headers=headers)
    assert r.status_code == 400
