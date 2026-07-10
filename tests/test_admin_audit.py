"""Tests for POST /api/admin/audit-schedule (admin-triggered auditor)."""

from datetime import datetime, timedelta, timezone

from models import db, Anime, Episode
from seed_dub_schedule import SYNTHETIC_TAG

SECRET = "s3cret"


def _headers():
    return {"X-Admin-Secret": SECRET, "Content-Type": "application/json"}


def _seed_current_week():
    """One synthetic dub episode inside the current schedule week."""
    anime = Anime(title="Audit Target", status="Currently Airing",
                  anilist_id=900, mal_id=901)
    db.session.add(anime)
    db.session.flush()
    db.session.add(
        Episode(
            anime_id=anime.id,
            episode_number=1,
            air_date_dub=(datetime.now(timezone.utc) + timedelta(days=1))
            .replace(tzinfo=None),
            dub_source=SYNTHETIC_TAG,
        )
    )
    db.session.commit()


def test_audit_schedule_requires_secret(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    resp = client.post("/api/admin/audit-schedule", json={})
    assert resp.status_code == 401


def test_audit_schedule_503_when_secret_unconfigured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_SYNC_SECRET", raising=False)
    resp = client.post("/api/admin/audit-schedule", json={},
                       headers=_headers())
    assert resp.status_code == 503


def test_audit_schedule_offline_returns_report(client, app, monkeypatch,
                                               tmp_path):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    monkeypatch.chdir(tmp_path)  # server-side report copy lands in tmp
    with app.app_context():
        _seed_current_week()
    resp = client.post(
        "/api/admin/audit-schedule",
        json={"weeks": 1, "offline": True},
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["totals"]["dub"]["entries"] == 1
    assert body["totals"]["dub"]["estimated"] == 1
    assert body["totals"]["synthetic_dub_fraction"] == 1.0
    assert "threshold_breaches" in body
    # 100% synthetic dub fraction must trip the documented 60% alarm.
    assert any("synthetic" in b for b in body["threshold_breaches"])
    assert {t["name"] for t in body["tiers"]} >= {"anilist", "animeschedule"}


def test_audit_schedule_clamps_weeks(client, app, monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    monkeypatch.chdir(tmp_path)
    resp = client.post(
        "/api/admin/audit-schedule",
        json={"weeks": 99, "offline": True},
        headers=_headers(),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    start = datetime.fromisoformat(body["window_start"])
    end = datetime.fromisoformat(body["window_end"])
    assert (end - start).days == 28  # clamped to 4 weeks
