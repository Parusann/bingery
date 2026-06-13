"""Tests for the dub-report endpoints (Plan 4 Task B3)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token

from models import Anime, DubReport, Episode, User, db


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_user(app, username: str, email: str) -> int:
    """Create a user, return its id."""
    bcrypt = Bcrypt(app)
    with app.app_context():
        u = User(
            username=username,
            email=email,
            password_hash=bcrypt.generate_password_hash("pw").decode("utf-8"),
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _token_for(app, user_id: int) -> str:
    with app.app_context():
        return create_access_token(identity=str(user_id))


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_anime_and_episode(app) -> tuple[int, int]:
    """Create an anime + one episode; return (anime_id, episode_id)."""
    with app.app_context():
        a = Anime(
            anilist_id=7001,
            title="Test Anime",
            title_english="Test Anime",
            synopsis="",
            year=2024,
            episodes=12,
            studio="S",
            image_url="",
            source="ORIGINAL",
            status="RELEASING",
        )
        db.session.add(a)
        db.session.commit()
        ep = Episode(anime_id=a.id, episode_number=1)
        db.session.add(ep)
        db.session.commit()
        return a.id, ep.id


# ─── POST /api/dub-reports ──────────────────────────────────────────────────


def test_post_requires_auth(client):
    resp = client.post("/api/dub-reports", json={})
    assert resp.status_code in (401, 422)  # JWT-Extended returns 401/422


def test_post_rejects_missing_episode_id(app, client):
    uid = _make_user(app, "u1", "u1@example.com")
    token = _token_for(app, uid)
    resp = client.post(
        "/api/dub-reports",
        json={"air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(token),
    )
    assert resp.status_code == 400
    assert "episode_id" in resp.get_json()["error"]


def test_post_rejects_unknown_episode(app, client):
    uid = _make_user(app, "u1", "u1@example.com")
    token = _token_for(app, uid)
    resp = client.post(
        "/api/dub-reports",
        json={"episode_id": 9999, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(token),
    )
    assert resp.status_code == 400
    assert "not found" in resp.get_json()["error"]


def test_post_rejects_invalid_air_date(app, client):
    _make_user(app, "admin", "admin@example.com")  # user 1
    uid = _make_user(app, "u2", "u2@example.com")  # user 2
    _, ep_id = _make_anime_and_episode(app)
    token = _token_for(app, uid)
    resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "not-a-date"},
        headers=_headers(token),
    )
    assert resp.status_code == 400
    assert "ISO" in resp.get_json()["error"]


def test_post_creates_pending_report(app, client):
    _make_user(app, "admin", "admin@example.com")
    uid = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    token = _token_for(app, uid)
    resp = client.post(
        "/api/dub-reports",
        json={
            "episode_id": ep_id,
            "air_date": "2026-06-01T12:00:00Z",
            "note": "seen the trailer",
        },
        headers=_headers(token),
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["report"]["status"] == "pending"
    assert body["report"]["episode_id"] == ep_id
    assert body["report"]["submitted_by"] == uid
    assert body["report"]["note"] == "seen the trailer"


def test_post_rejects_duplicate_submission_409(app, client):
    _make_user(app, "admin", "admin@example.com")
    uid = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    token = _token_for(app, uid)
    payload = {
        "episode_id": ep_id,
        "air_date": "2026-06-01T12:00:00Z",
    }
    first = client.post("/api/dub-reports", json=payload, headers=_headers(token))
    assert first.status_code == 201
    second = client.post("/api/dub-reports", json=payload, headers=_headers(token))
    assert second.status_code == 409
    assert "already" in second.get_json()["error"].lower()


def test_post_rejects_overlong_note(app, client):
    _make_user(app, "admin", "admin@example.com")
    uid = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    token = _token_for(app, uid)
    resp = client.post(
        "/api/dub-reports",
        json={
            "episode_id": ep_id,
            "air_date": "2026-06-01T12:00:00Z",
            "note": "x" * 501,
        },
        headers=_headers(token),
    )
    assert resp.status_code == 400


# ─── GET /api/dub-reports ───────────────────────────────────────────────────


def test_get_requires_admin(app, client):
    _make_user(app, "admin", "admin@example.com")  # user 1
    uid = _make_user(app, "u2", "u2@example.com")  # user 2 (non-admin)
    token = _token_for(app, uid)
    resp = client.get("/api/dub-reports", headers=_headers(token))
    assert resp.status_code == 403


def test_get_admin_lists_reports(app, client):
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)

    client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )

    resp = client.get("/api/dub-reports", headers=_headers(admin_token))
    assert resp.status_code == 200
    reports = resp.get_json()["reports"]
    assert len(reports) == 1
    assert reports[0]["episode_id"] == ep_id


def test_get_filters_by_status(app, client):
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    admin_token = _token_for(app, admin_id)

    # Create a pending report directly.
    with app.app_context():
        db.session.add(
            DubReport(
                episode_id=ep_id,
                submitted_by=submitter_id,
                air_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
                status="pending",
            )
        )
        db.session.add(
            DubReport(
                episode_id=ep_id,
                submitted_by=admin_id,
                air_date=datetime(2026, 6, 2, tzinfo=timezone.utc),
                status="accepted",
            )
        )
        db.session.commit()

    resp = client.get(
        "/api/dub-reports?status=pending", headers=_headers(admin_token)
    )
    assert resp.status_code == 200
    reports = resp.get_json()["reports"]
    assert len(reports) == 1
    assert reports[0]["status"] == "pending"


# ─── PATCH /api/dub-reports/<id> ────────────────────────────────────────────


def test_patch_requires_admin(app, client):
    _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]

    resp = client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "accepted"},
        headers=_headers(sub_token),
    )
    assert resp.status_code == 403


def test_patch_unknown_report_returns_404(app, client):
    admin_id = _make_user(app, "admin", "admin@example.com")
    admin_token = _token_for(app, admin_id)
    resp = client.patch(
        "/api/dub-reports/9999",
        json={"status": "accepted"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 404


def test_patch_rejects_invalid_status(app, client):
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]

    resp = client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "garbage"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 400


def test_patch_accept_writes_episode_air_date_dub(app, client):
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]

    resp = client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "accepted"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["report"]["status"] == "accepted"
    assert body["report"]["reviewed_by"] == admin_id

    with app.app_context():
        episode = db.session.get(Episode, ep_id)
        assert episode.air_date_dub is not None
        assert episode.air_date_dub.year == 2026
        assert episode.air_date_dub.month == 6
        assert episode.dub_source == "user:u2"


def test_patch_accept_overrides_existing_dub_source(app, client):
    """Tier 3 (user) must override Tier 1/2 when an admin accepts."""
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    with app.app_context():
        ep = db.session.get(Episode, ep_id)
        ep.air_date_dub = datetime(2026, 5, 1, tzinfo=timezone.utc)
        ep.dub_source = "crunchyroll_rss"
        db.session.commit()

    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-15T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]

    resp = client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "accepted"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200

    with app.app_context():
        episode = db.session.get(Episode, ep_id)
        assert episode.air_date_dub.month == 6
        assert episode.air_date_dub.day == 15
        assert episode.dub_source == "user:u2"


def test_patch_reject_does_not_touch_episode(app, client):
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]

    resp = client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "rejected"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["report"]["status"] == "rejected"

    with app.app_context():
        episode = db.session.get(Episode, ep_id)
        assert episode.air_date_dub is None
        assert episode.dub_source is None


def test_patch_reject_reverts_previously_accepted_override(app, client):
    """Rejecting a report that was already accepted must undo the episode
    dub override it wrote — otherwise rejected data lingers on the episode."""
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]

    client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "accepted"},
        headers=_headers(admin_token),
    )
    # Now reject the same (accepted) report.
    resp = client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "rejected"},
        headers=_headers(admin_token),
    )
    assert resp.status_code == 200

    with app.app_context():
        episode = db.session.get(Episode, ep_id)
        assert episode.air_date_dub is None
        assert episode.dub_source is None


def test_patch_reject_does_not_clobber_other_source(app, client):
    """If a sync feed (not this report) currently owns the episode's dub
    date, rejecting the report must not wipe that feed's data."""
    admin_id = _make_user(app, "admin", "admin@example.com")
    submitter_id = _make_user(app, "u2", "u2@example.com")
    _, ep_id = _make_anime_and_episode(app)
    sub_token = _token_for(app, submitter_id)
    admin_token = _token_for(app, admin_id)
    create_resp = client.post(
        "/api/dub-reports",
        json={"episode_id": ep_id, "air_date": "2026-06-01T12:00:00Z"},
        headers=_headers(sub_token),
    )
    report_id = create_resp.get_json()["report"]["id"]
    client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "accepted"},
        headers=_headers(admin_token),
    )
    # A sync feed overwrites the dub source after acceptance.
    with app.app_context():
        ep = db.session.get(Episode, ep_id)
        ep.dub_source = "crunchyroll_rss"
        db.session.commit()

    client.patch(
        f"/api/dub-reports/{report_id}",
        json={"status": "rejected"},
        headers=_headers(admin_token),
    )
    with app.app_context():
        episode = db.session.get(Episode, ep_id)
        assert episode.dub_source == "crunchyroll_rss"
        assert episode.air_date_dub is not None
