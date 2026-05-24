"""Tests for GET /api/schedule/week — week-anchored day-of-week schedule.

Uses the project conftest fixtures (`app`, `client`, `auth_headers`). DB writes
go through `db.session` directly — no `db_session` fixture in this repo.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from models import db, User, Anime, Episode, WatchlistEntry


@pytest.fixture()
def user(app):
    with app.app_context():
        u = User(email="sched@test.local", username="sched", password_hash="x")
        db.session.add(u)
        db.session.commit()
        return {"id": u.id, "email": u.email}


@pytest.fixture()
def auth_headers_for(client, user):
    res = client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "wrong"},
    )
    # We don't have a real password — login fails. Build a JWT manually instead.
    from flask_jwt_extended import create_access_token
    from app import create_app
    # Use the same app's token
    return None  # placeholder, see helper below


def _auth(app, user_id):
    """Generate a header dict carrying a valid JWT for the given user_id."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def test_week_param_required(client, app, user):
    res = client.get("/api/schedule/week", headers=_auth(app, user["id"]))
    assert res.status_code == 400


def test_week_param_garbage(client, app, user):
    res = client.get(
        "/api/schedule/week?week=not-a-date",
        headers=_auth(app, user["id"]),
    )
    assert res.status_code == 400


def test_week_returns_seven_empty_days(client, app, user):
    """With no Episode rows, response is well-formed with 7 empty day buckets."""
    res = client.get(
        "/api/schedule/week?week=2026-05-24",
        headers=_auth(app, user["id"]),
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["week_start"] == "2026-05-24"
    assert len(body["days"]) == 7
    expected_dates = [
        "2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27",
        "2026-05-28", "2026-05-29", "2026-05-30",
    ]
    assert [d["date"] for d in body["days"]] == expected_dates
    for d in body["days"]:
        assert d["episodes"] == []
