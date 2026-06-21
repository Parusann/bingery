"""Invite-code gating on POST /api/auth/register (SIGNUP_INVITE_CODE)."""


def test_register_open_when_code_unset(client, sent_codes, monkeypatch):
    monkeypatch.delenv("SIGNUP_INVITE_CODE", raising=False)
    r = client.post(
        "/api/auth/register",
        json={
            "username": "openuser",
            "email": "open@example.com",
            "password": "password123",
        },
    )
    assert r.status_code == 202, r.get_json()


def test_register_blocked_without_code(client, sent_codes, monkeypatch):
    monkeypatch.setenv("SIGNUP_INVITE_CODE", "letmein")
    r = client.post(
        "/api/auth/register",
        json={
            "username": "gateduser",
            "email": "gated@example.com",
            "password": "password123",
        },
    )
    assert r.status_code == 403
    assert sent_codes == []  # no verification email on a blocked signup


def test_register_blocked_with_wrong_code(client, sent_codes, monkeypatch):
    monkeypatch.setenv("SIGNUP_INVITE_CODE", "letmein")
    r = client.post(
        "/api/auth/register",
        json={
            "username": "wrongcode",
            "email": "wrong@example.com",
            "password": "password123",
            "invite_code": "nope",
        },
    )
    assert r.status_code == 403


def test_register_allowed_with_correct_code(client, sent_codes, monkeypatch):
    monkeypatch.setenv("SIGNUP_INVITE_CODE", "letmein")
    r = client.post(
        "/api/auth/register",
        json={
            "username": "rightcode",
            "email": "right@example.com",
            "password": "password123",
            "invite_code": "letmein",
        },
    )
    assert r.status_code == 202, r.get_json()
    assert len(sent_codes) == 1  # verification email sent on success
