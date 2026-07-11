"""Tests for the schedule-window anti-drift refresh (sync_anilist.window_refresh
and POST /api/anilist/sync mode="window")."""

from datetime import datetime, timedelta, timezone

import sync_anilist
from models import db, Anime, Episode

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _mk(title, status, anilist_id, last_sub_delta_days):
    anime = Anime(title=title, status=status, anilist_id=anilist_id)
    db.session.add(anime)
    db.session.flush()
    db.session.add(Episode(
        anime_id=anime.id, episode_number=1,
        air_date_sub=NOW + timedelta(days=last_sub_delta_days),
    ))
    return anime


def test_window_cohort_selects_drift_candidates_longest_quiet_first(
    app, monkeypatch
):
    with app.app_context():
        _mk("Quiet Two Weeks", "Currently Airing", 101, -14)
        _mk("Aired Yesterday", "Currently Airing", 102, -1)
        _mk("Premieres Soon", "Upcoming", 103, +5)
        # A finished-marked show with window episodes is INCLUDED: if that
        # status is wrong, the serving guards are silently hiding real
        # episodes and only a refresh can heal it.
        _mk("Marked Finished", "Finished Airing", 104, -3)
        _mk("Long Gone", "Currently Airing", 105, -90)        # excluded: window
        _mk("Far Future", "Upcoming", 106, +90)               # excluded: window
        no_id = Anime(title="No AniList Id", status="Currently Airing")
        db.session.add(no_id)
        db.session.flush()
        db.session.add(Episode(anime_id=no_id.id, episode_number=1,
                               air_date_sub=NOW))               # excluded: null id
        db.session.commit()

        captured = {}

        def fake_sync_ids(client, ids, dry_run=False):
            captured["ids"] = list(ids)
            return {"requested": len(ids), "synced": len(ids), "failed": 0}

        monkeypatch.setattr(sync_anilist, "sync_ids", fake_sync_ids)
        summary = sync_anilist.window_refresh(object())

    # Window cohort ordered by how long each show has been quiet.
    assert captured["ids"] == [101, 104, 102, 103]
    assert summary["cohort"] == 4
    assert summary["refreshed"] == 4
    assert summary["capped"] is False


def test_window_cap_is_loud_and_keeps_longest_quiet(app, monkeypatch, capsys):
    with app.app_context():
        _mk("Quietest", "Currently Airing", 201, -20)
        _mk("Quieter", "Currently Airing", 202, -10)
        _mk("Recent", "Currently Airing", 203, -1)
        db.session.commit()

        monkeypatch.setattr(
            sync_anilist, "sync_ids",
            lambda client, ids, dry_run=False: {
                "requested": len(ids), "synced": len(ids), "failed": 0,
            },
        )
        summary = sync_anilist.window_refresh(object(), max_ids=2)

    out = capsys.readouterr().out
    assert summary["capped"] is True
    assert summary["refreshed"] == 2
    assert summary["cohort"] == 3
    assert "COVERAGE CAP" in out


def test_sync_endpoint_window_mode(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.AniListClient", lambda: object())

    seen = {}

    def fake_window_refresh(client_obj, **kwargs):
        seen.update(kwargs)
        return {"requested": 3, "synced": 3, "failed": 0,
                "cohort": 3, "refreshed": 3, "capped": False,
                "days_back": kwargs["days_back"],
                "days_forward": kwargs["days_forward"]}

    monkeypatch.setattr("sync_anilist.window_refresh", fake_window_refresh)
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "window", "days_back": 30, "max_ids": 999},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["mode"] == "window"
    assert body["synced"] == 3
    assert seen["days_back"] == 30
    assert seen["max_ids"] == 120      # clamped from 999 (gunicorn budget)
    assert seen["days_forward"] == 28  # default


def test_sync_endpoint_window_mode_rejects_bad_ints(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "window", "days_back": "soon"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 400


def test_sync_endpoint_window_mode_requires_secret(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    r = client.post("/api/anilist/sync", json={"mode": "window"})
    assert r.status_code == 401


def test_sync_endpoint_window_errors_do_not_leak_exception_text(
    client, monkeypatch
):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.AniListClient", lambda: object())

    def boom(*a, **k):
        raise RuntimeError("secret internals: /data/bingery.db")

    monkeypatch.setattr("sync_anilist.window_refresh", boom)
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "window"},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 502
    body = r.get_json()
    assert body == {"error": "Window refresh failed."}
    assert "secret internals" not in r.get_data(as_text=True)


def test_sync_endpoint_window_clamps_lower_bounds(client, monkeypatch):
    monkeypatch.setenv("ADMIN_SYNC_SECRET", "s3cret")
    monkeypatch.setattr("utils.anilist.AniListClient", lambda: object())
    seen = {}

    def fake(client_obj, **kwargs):
        seen.update(kwargs)
        return {"requested": 0, "synced": 0, "failed": 0,
                "cohort": 0, "refreshed": 0, "capped": False}

    monkeypatch.setattr("sync_anilist.window_refresh", fake)
    r = client.post(
        "/api/anilist/sync",
        json={"mode": "window", "days_back": 0, "days_forward": -5,
              "max_ids": 1},
        headers={"X-Admin-Secret": "s3cret"},
    )
    assert r.status_code == 200
    assert seen == {"days_back": 1, "days_forward": 1, "max_ids": 10}


def test_window_refresh_forwards_dry_run(app, monkeypatch):
    with app.app_context():
        _mk("Dry Run Show", "Currently Airing", 301, -2)
        db.session.commit()
        captured = {}

        def fake_sync_ids(client, ids, dry_run=False):
            captured["dry_run"] = dry_run
            captured["ids"] = list(ids)
            return {"requested": len(ids), "synced": 0, "failed": 0}

        monkeypatch.setattr(sync_anilist, "sync_ids", fake_sync_ids)
        sync_anilist.window_refresh(object(), dry_run=True)

    assert captured["dry_run"] is True
    assert captured["ids"] == [301]


def test_cli_window_branch_exit_codes(app, monkeypatch):
    calls = {}

    def fake_window_refresh(client, dry_run=False):
        calls["dry_run"] = dry_run
        return calls["summary"]

    monkeypatch.setattr(sync_anilist, "window_refresh", fake_window_refresh)

    calls["summary"] = {"requested": 3, "synced": 3, "failed": 0}
    assert sync_anilist.main(["--window", "--dry-run"]) == 0
    assert calls["dry_run"] is True

    # Empty cohort is success, not failure.
    calls["summary"] = {"requested": 0, "synced": 0, "failed": 0}
    assert sync_anilist.main(["--window"]) == 0

    # Every requested id failing is a failure exit.
    calls["summary"] = {"requested": 3, "synced": 0, "failed": 3}
    assert sync_anilist.main(["--window"]) == 1
