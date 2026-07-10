"""Tests for the dub-tier doctor (utils/dub_doctor.py + admin endpoints)."""

from datetime import datetime, timedelta, timezone

from models import db, Anime, Episode
from seed_dub_schedule import SYNTHETIC_TAG
from utils.dub_doctor import dub_tier_health

SECRET = "s3cret"


def _headers():
    return {"X-Admin-Secret": SECRET}


def _seed(dub_source, days_ahead=3, episode_number=1):
    anime = Anime(title=f"Doctor {dub_source} {episode_number}",
                  status="Currently Airing")
    db.session.add(anime)
    db.session.flush()
    db.session.add(
        Episode(
            anime_id=anime.id,
            episode_number=episode_number,
            air_date_dub=(datetime.now(timezone.utc)
                          + timedelta(days=days_ahead)).replace(tzinfo=None),
            dub_source=dub_source,
        )
    )
    db.session.commit()


def test_missing_key_marks_animeschedule_dark(app, monkeypatch):
    monkeypatch.delenv("ANIMESCHEDULE_API_KEY", raising=False)
    with app.app_context():
        report = dub_tier_health()
    tier = next(t for t in report["tiers"] if t["tier"] == "animeschedule")
    assert tier["state"] == "dark"
    assert "ANIMESCHEDULE_API_KEY" in tier["detail"]
    assert any("animeschedule" in a for a in report["alarms"])
    assert report["healthy"] is False


def test_present_key_is_not_dark(app, monkeypatch):
    monkeypatch.setenv("ANIMESCHEDULE_API_KEY", "token")
    with app.app_context():
        report = dub_tier_health()
    tier = next(t for t in report["tiers"] if t["tier"] == "animeschedule")
    assert tier["state"] != "dark"


def test_synthetic_fraction_alarm(app, monkeypatch):
    monkeypatch.setenv("ANIMESCHEDULE_API_KEY", "token")
    with app.app_context():
        for i in range(3):
            _seed(SYNTHETIC_TAG, episode_number=i + 1)
        report = dub_tier_health()
    up = report["upcoming_14d"]
    assert up["dub_entries"] == 3
    assert up["synthetic"] == 3
    assert up["synthetic_fraction"] == 1.0
    assert any("synthetic fraction" in a for a in report["alarms"])


def test_real_rows_keep_fraction_low(app, monkeypatch):
    monkeypatch.setenv("ANIMESCHEDULE_API_KEY", "token")
    with app.app_context():
        _seed("crunchyroll_rss", episode_number=1)
        _seed("animeschedule", episode_number=2)
        report = dub_tier_health()
    assert report["upcoming_14d"]["synthetic_fraction"] == 0.0
    cr = next(t for t in report["tiers"] if t["tier"] == "crunchyroll_rss")
    assert cr["state"] == "live"  # wrote within the stale window
    assert report["healthy"] is True


def test_dub_doctor_endpoint_secret_gated(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    assert client.get("/api/admin/dub-doctor").status_code == 401
    resp = client.get("/api/admin/dub-doctor", headers=_headers())
    assert resp.status_code == 200
    body = resp.get_json()
    assert {t["tier"] for t in body["tiers"]} == {
        "crunchyroll_rss", "animeschedule", "research", "user_reports",
    }


def test_sync_cli_fails_loudly_without_key(monkeypatch, capsys):
    import sync_dub_animeschedule

    monkeypatch.delenv("ANIMESCHEDULE_API_KEY", raising=False)
    rc = sync_dub_animeschedule.main([])
    out = capsys.readouterr().out
    assert rc == 2
    assert "TIER DARK" in out
    assert "ANIMESCHEDULE_API_KEY" in out
