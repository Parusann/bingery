"""Smoke tests for Episode and AniListSyncState models."""
from datetime import datetime, timezone

import pytest

from models import (
    db,
    Anime,
    Episode,
    DubReport,
    User,
    AniListSyncState,
    get_or_create_sync_state,
)


def _make_anime(app, anilist_id=1, title="Test Anime"):
    with app.app_context():
        a = Anime(
            anilist_id=anilist_id,
            title=title,
            synopsis="",
            year=2024,
            episodes=12,
            studio="S",
            image_url="",
            source="ORIGINAL",
            status="Currently Airing",
        )
        db.session.add(a)
        db.session.commit()
        return a.id


# ─── Episode ─────────────────────────────────────────────────────────────────


def test_create_episode(app):
    aid = _make_anime(app)
    with app.app_context():
        ep = Episode(
            anime_id=aid,
            episode_number=1,
            air_date_sub=datetime(2024, 4, 5, 14, 30, tzinfo=timezone.utc),
            sub_source="anilist",
        )
        db.session.add(ep)
        db.session.commit()
        assert ep.id is not None
        assert ep.created_at is not None
        assert ep.updated_at is not None


def test_episode_to_dict_includes_iso_timestamps(app):
    aid = _make_anime(app)
    with app.app_context():
        ep = Episode(
            anime_id=aid,
            episode_number=3,
            air_date_sub=datetime(2024, 4, 19, 14, 30, tzinfo=timezone.utc),
        )
        db.session.add(ep)
        db.session.commit()
        d = ep.to_dict()
        assert d["episode_number"] == 3
        assert d["anime_id"] == aid
        assert d["air_date_sub"].startswith("2024-04-19")
        assert d["air_date_dub"] is None
        assert "id" in d


def test_episode_unique_constraint_anime_id_and_number(app):
    aid = _make_anime(app)
    with app.app_context():
        db.session.add(Episode(anime_id=aid, episode_number=1))
        db.session.commit()
        with pytest.raises(Exception):
            db.session.add(Episode(anime_id=aid, episode_number=1))
            db.session.commit()
        db.session.rollback()


def test_episode_nullable_dub_fields(app):
    aid = _make_anime(app)
    with app.app_context():
        ep = Episode(anime_id=aid, episode_number=2)
        db.session.add(ep)
        db.session.commit()
        assert ep.air_date_dub is None
        assert ep.dub_source is None
        assert ep.sub_source == "anilist"


# ─── AniListSyncState ────────────────────────────────────────────────────────


def test_create_sync_state(app):
    with app.app_context():
        state = AniListSyncState(
            last_page=5,
            total_synced=250,
            status="idle",
        )
        db.session.add(state)
        db.session.commit()
        assert state.id is not None
        assert state.last_page == 5
        assert state.total_synced == 250
        assert state.status == "idle"


def test_sync_state_to_dict(app):
    with app.app_context():
        state = AniListSyncState(
            last_page=2,
            last_run_at=datetime(2026, 5, 13, 9, 0, tzinfo=timezone.utc),
            total_synced=100,
            status="running",
        )
        db.session.add(state)
        db.session.commit()
        d = state.to_dict()
        assert d["last_page"] == 2
        assert d["status"] == "running"
        assert d["total_synced"] == 100
        assert d["last_run_at"].startswith("2026-05-13")
        assert d["last_full_at"] is None


def test_get_or_create_sync_state_creates_singleton(app):
    with app.app_context():
        assert AniListSyncState.query.count() == 0
        state = get_or_create_sync_state()
        assert state is not None
        assert state.id is not None
        assert state.last_page == 0
        assert state.status == "idle"
        assert state.total_synced == 0
        assert AniListSyncState.query.count() == 1


def test_get_or_create_sync_state_returns_existing(app):
    with app.app_context():
        first = get_or_create_sync_state()
        first.last_page = 42
        first.total_synced = 2100
        db.session.commit()

        second = get_or_create_sync_state()
        assert second.id == first.id
        assert second.last_page == 42
        assert second.total_synced == 2100
        assert AniListSyncState.query.count() == 1


def test_sync_state_error_status_with_message(app):
    with app.app_context():
        state = get_or_create_sync_state()
        state.status = "error"
        state.error_message = "AniList API returned 502"
        db.session.commit()

        refetched = get_or_create_sync_state()
        assert refetched.status == "error"
        assert refetched.error_message == "AniList API returned 502"


# ─── DubReport ───────────────────────────────────────────────────────────────


def _make_user(app, username="u1", email="u1@example.com"):
    with app.app_context():
        u = User(username=username, email=email, password_hash="x")
        db.session.add(u)
        db.session.commit()
        return u.id


def _make_episode(app, anime_id, episode_number=1):
    with app.app_context():
        ep = Episode(anime_id=anime_id, episode_number=episode_number)
        db.session.add(ep)
        db.session.commit()
        return ep.id


def test_create_dub_report_defaults_pending(app):
    aid = _make_anime(app)
    eid = _make_episode(app, aid)
    uid = _make_user(app)
    with app.app_context():
        report = DubReport(
            episode_id=eid,
            submitted_by=uid,
            air_date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        )
        db.session.add(report)
        db.session.commit()
        fetched = db.session.get(DubReport, report.id)
        assert fetched.status == "pending"
        assert fetched.note is None
        assert fetched.reviewed_by is None
        assert fetched.created_at is not None


def test_dub_report_to_dict_iso_timestamps(app):
    aid = _make_anime(app)
    eid = _make_episode(app, aid)
    uid = _make_user(app)
    with app.app_context():
        report = DubReport(
            episode_id=eid,
            submitted_by=uid,
            air_date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            note="seen on Crunchyroll trailer",
        )
        db.session.add(report)
        db.session.commit()
        d = report.to_dict()
        assert d["episode_id"] == eid
        assert d["submitted_by"] == uid
        assert d["air_date"].startswith("2026-06-01T12:00:00")
        assert d["status"] == "pending"
        assert d["note"] == "seen on Crunchyroll trailer"
        assert d["reviewed_at"] is None


def test_dub_report_relationships_resolve(app):
    aid = _make_anime(app)
    eid = _make_episode(app, aid)
    submitter_id = _make_user(app, username="submitter", email="s@example.com")
    reviewer_id = _make_user(app, username="reviewer", email="r@example.com")
    with app.app_context():
        report = DubReport(
            episode_id=eid,
            submitted_by=submitter_id,
            reviewed_by=reviewer_id,
            air_date=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            status="accepted",
            reviewed_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        db.session.add(report)
        db.session.commit()
        fetched = db.session.get(DubReport, report.id)
        assert fetched.episode.id == eid
        assert fetched.submitter.username == "submitter"
        assert fetched.reviewer.username == "reviewer"


def test_dub_report_cascade_when_anime_deleted(app):
    aid = _make_anime(app)
    eid = _make_episode(app, aid)
    uid = _make_user(app)
    with app.app_context():
        report = DubReport(
            episode_id=eid,
            submitted_by=uid,
            air_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        db.session.add(report)
        db.session.commit()
        report_id = report.id
        assert db.session.get(DubReport, report_id) is not None
        assert db.session.get(Episode, eid) is not None

        anime = db.session.get(Anime, aid)
        db.session.delete(anime)
        db.session.commit()

        assert db.session.get(Anime, aid) is None
        assert db.session.get(Episode, eid) is None
        assert db.session.get(DubReport, report_id) is None


def test_dub_report_cascade_when_episode_deleted(app):
    aid = _make_anime(app)
    eid = _make_episode(app, aid)
    uid = _make_user(app)
    with app.app_context():
        report = DubReport(
            episode_id=eid,
            submitted_by=uid,
            air_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        db.session.add(report)
        db.session.commit()
        report_id = report.id

        ep = db.session.get(Episode, eid)
        db.session.delete(ep)
        db.session.commit()

        assert db.session.get(Episode, eid) is None
        assert db.session.get(DubReport, report_id) is None


def test_user_has_taste_profile_cache_column(app):
    with app.app_context():
        u = User(email="x@x.com", username="x", password_hash="x")
        u.taste_profile_cache = '{"foo": 1}'
        db.session.add(u)
        db.session.commit()
        fetched = User.query.filter_by(email="x@x.com").first()
        assert fetched.taste_profile_cache == '{"foo": 1}'


def test_anime_has_popularity_column(app):
    with app.app_context():
        a = Anime(title="Test Anime", anilist_id=999999, popularity=12345)
        db.session.add(a)
        db.session.commit()
        fetched = Anime.query.filter_by(anilist_id=999999).first()
        assert fetched.popularity == 12345
        assert fetched.to_dict()["popularity"] == 12345
