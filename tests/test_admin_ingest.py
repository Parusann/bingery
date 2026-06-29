"""Tests for POST /api/admin/ingest-dub-dates (research/manual dub ingest)."""
from datetime import datetime, timezone

SECRET = "testsecret"


def _hdr():
    return {"X-Admin-Secret": SECRET, "Content-Type": "application/json"}


def _seed_anime(app, **kw):
    from models import db, Anime
    d = dict(title="Test", status="RELEASING")
    d.update(kw)
    with app.app_context():
        a = Anime(**d)
        db.session.add(a)
        db.session.commit()
        return a.id


def _seed_ep(app, *, anime_id, n, dub=None, src=None):
    from models import db, Episode
    with app.app_context():
        e = Episode(anime_id=anime_id, episode_number=n, air_date_dub=dub, dub_source=src)
        db.session.add(e)
        db.session.commit()
        return e.id


def _get_ep(app, ep_id):
    from models import db, Episode
    with app.app_context():
        e = db.session.get(Episode, ep_id)
        return e.air_date_dub, e.dub_source


def test_ingest_requires_secret(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    _seed_anime(app, anilist_id=111)
    r = client.post("/api/admin/ingest-dub-dates", json={"rows": []})  # no header
    assert r.status_code == 401


def test_ingest_503_when_secret_unset(client, app, monkeypatch):
    monkeypatch.delenv("ADMIN_SYNC_SECRET", raising=False)
    r = client.post("/api/admin/ingest-dub-dates", headers=_hdr(), json={"rows": []})
    assert r.status_code == 503


def test_ingest_bad_body(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    r = client.post("/api/admin/ingest-dub-dates", headers=_hdr(), json={"nope": 1})
    assert r.status_code == 400


def test_ingest_by_anilist_id_fills_null(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    aid = _seed_anime(app, title="By Id", anilist_id=222)
    ep = _seed_ep(app, anime_id=aid, n=1)  # no dub yet
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={"rows": [{"anilist_id": 222, "episode_number": 1, "air_date": "2026-07-01T15:00:00Z"}]},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["matched"] == 1
    assert body["written"] == 1
    dub, src = _get_ep(app, ep)
    assert src == "research"
    assert dub is not None


def test_ingest_overrides_synthetic(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    aid = _seed_anime(app, title="Synthy", anilist_id=333)
    synthetic = datetime(2026, 9, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    ep = _seed_ep(app, anime_id=aid, n=2, dub=synthetic, src="synthetic_lag_8w")
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={"rows": [{"anilist_id": 333, "episode_number": 2, "air_date": "2026-06-10T12:00:00Z"}]},
    )
    assert r.get_json()["written"] == 1
    _, src = _get_ep(app, ep)
    assert src == "research"


def test_ingest_protects_real_source_unless_overwrite(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    aid = _seed_anime(app, title="Real", anilist_id=444)
    existing = datetime(2026, 7, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    ep = _seed_ep(app, anime_id=aid, n=1, dub=existing, src="crunchyroll_rss")

    # Without overwrite → the authoritative source is preserved.
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={"rows": [{"anilist_id": 444, "episode_number": 1, "air_date": "2026-06-10T12:00:00Z"}]},
    )
    body = r.get_json()
    assert body["skipped_protected"] == 1
    assert body["written"] == 0
    _, src = _get_ep(app, ep)
    assert src == "crunchyroll_rss"

    # With overwrite → replaced.
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={
            "rows": [{"anilist_id": 444, "episode_number": 1, "air_date": "2026-06-10T12:00:00Z"}],
            "overwrite": True,
        },
    )
    assert r.get_json()["written"] == 1
    _, src = _get_ep(app, ep)
    assert src == "research"


def test_ingest_creates_missing_episode(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    aid = _seed_anime(app, title="NewEp", anilist_id=555)
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={"rows": [{"anilist_id": 555, "episode_number": 9, "air_date": "2026-07-01T00:00:00Z"}]},
    )
    assert r.get_json()["written"] == 1
    from models import db, Episode
    with app.app_context():
        e = Episode.query.filter_by(anime_id=aid, episode_number=9).first()
        assert e is not None
        assert e.dub_source == "research"


def test_ingest_by_title_fuzzy(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    aid = _seed_anime(app, title="Spy x Family", anilist_id=666)
    _seed_ep(app, anime_id=aid, n=3)
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={"rows": [{"title": "Spy x Family", "episode_number": 3, "air_date": "2026-07-01T00:00:00Z"}]},
    )
    body = r.get_json()
    assert body["matched"] == 1
    assert body["written"] == 1


def test_ingest_unmatched_reported(client, app, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", SECRET)
    _seed_anime(app, title="Totally Different Show", anilist_id=777)
    r = client.post(
        "/api/admin/ingest-dub-dates",
        headers=_hdr(),
        json={"rows": [{"title": "Nonexistent Zzz Qqq", "episode_number": 1, "air_date": "2026-07-01T00:00:00Z"}]},
    )
    body = r.get_json()
    assert body["unmatched"] == 1
    assert body["written"] == 0
