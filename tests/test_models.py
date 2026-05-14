"""Smoke tests for Episode and AniListSyncState models."""
from datetime import datetime, timezone

import pytest

from models import (
    db,
    Anime,
    Episode,
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
