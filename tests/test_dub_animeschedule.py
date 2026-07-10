"""Tests for the AnimeSchedule.net dub ingester (Plan 4 Task B2b)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import responses

from models import Anime, Episode, db
from utils.dub_sources.animeschedule import (
    ANIMESCHEDULE_URL,
    DUB_SOURCE,
    fetch_payload,
    ingest_payload,
    parse_payload,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


JSON_FIXTURE_LIST = json.dumps(
    [
        {
            "title": "Attack on Titan",
            "english": "Attack on Titan",
            "episodeNumber": 12,
            "episodeDate": "2026-05-11T21:00:00Z",
        },
        {
            "title": "Boku no Hero Academia",
            "english": "My Hero Academia",
            "episodeNumber": 3,
            "episodeDate": "2026-05-12T19:30:00+00:00",
        },
        {
            "title": "Kimetsu no Yaiba",
            "english": "Demon Slayer",
            "episodeNumber": 5,
            "episodeDate": "2026-05-13T18:00:00Z",
        },
        {
            "title": "Some Totally Random Show",
            "english": None,
            "episodeNumber": 1,
            "episodeDate": "2026-05-14T12:00:00Z",
        },
        {
            "title": "Missing Episode Number Show",
            "english": "Missing Episode Number Show",
            "episodeNumber": None,
            "episodeDate": "2026-05-14T13:00:00Z",
        },
    ]
)

JSON_FIXTURE_ENVELOPE = json.dumps(
    {
        "results": [
            {
                "title": "Attack on Titan",
                "episodeNumber": 13,
                "episodeDate": "2026-05-18T21:00:00Z",
            }
        ]
    }
)


def _seed_anime(app):
    with app.app_context():
        rows = [
            Anime(
                anilist_id=2001,
                title="Attack on Titan",
                title_english="Attack on Titan",
                synopsis="",
                year=2013,
                episodes=25,
                studio="WIT",
                image_url="",
                source="MANGA",
                status="FINISHED",
            ),
            Anime(
                anilist_id=2002,
                title="Boku no Hero Academia",
                title_english="My Hero Academia",
                synopsis="",
                year=2016,
                episodes=13,
                studio="Bones",
                image_url="",
                source="MANGA",
                status="RELEASING",
            ),
            Anime(
                anilist_id=2003,
                title="Kimetsu no Yaiba",
                title_english="Demon Slayer",
                synopsis="",
                year=2019,
                episodes=26,
                studio="ufotable",
                image_url="",
                source="MANGA",
                status="RELEASING",
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()
        return {r.anilist_id: r.id for r in rows}


# ─── Parsing ─────────────────────────────────────────────────────────────────


def test_parse_payload_list_top_level():
    entries = parse_payload(JSON_FIXTURE_LIST)
    assert len(entries) == 5
    aot = next(e for e in entries if e.title == "Attack on Titan")
    assert aot.english_title == "Attack on Titan"
    assert aot.episode_number == 12
    assert aot.air_date.year == 2026 and aot.air_date.day == 11
    assert aot.air_date.tzinfo == timezone.utc


def test_parse_payload_envelope_results():
    entries = parse_payload(JSON_FIXTURE_ENVELOPE)
    assert len(entries) == 1
    assert entries[0].episode_number == 13


def test_parse_payload_handles_missing_fields():
    bad = json.dumps([{"title": "OK"}, {"english": "no title"}, {}])
    # All rows lack a valid date — should yield 0.
    assert parse_payload(bad) == []


def test_parse_payload_z_suffix_iso_date():
    entries = parse_payload(JSON_FIXTURE_LIST)
    aot = next(e for e in entries if e.title == "Attack on Titan")
    assert aot.air_date == datetime(2026, 5, 11, 21, 0, tzinfo=timezone.utc)


def test_parse_payload_invalid_top_level_type():
    assert parse_payload(json.dumps("a string")) == []
    assert parse_payload(json.dumps(42)) == []


# ─── Ingest end-to-end ───────────────────────────────────────────────────────


def test_ingest_writes_when_air_date_dub_is_null(app):
    ids = _seed_anime(app)
    with app.app_context():
        summary = ingest_payload(JSON_FIXTURE_LIST, dry_run=False)
        aot_ep = (
            Episode.query
            .filter_by(anime_id=ids[2001], episode_number=12)
            .first()
        )
        assert aot_ep is not None
        assert aot_ep.dub_source == DUB_SOURCE
        assert aot_ep.air_date_dub.year == 2026
    assert summary["written"] >= 3
    assert summary["unmatched"] >= 1


def test_ingest_does_not_overwrite_existing_dub(app):
    ids = _seed_anime(app)
    existing_dub = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    with app.app_context():
        ep = Episode(
            anime_id=ids[2001],
            episode_number=12,
            air_date_dub=existing_dub,
            dub_source="crunchyroll_rss",
        )
        db.session.add(ep)
        db.session.commit()

        summary = ingest_payload(JSON_FIXTURE_LIST, dry_run=False)
        refreshed = (
            Episode.query
            .filter_by(anime_id=ids[2001], episode_number=12)
            .first()
        )
        # SQLite strips tzinfo on readback; compare naive parts.
        assert refreshed.air_date_dub.replace(tzinfo=None) == existing_dub.replace(tzinfo=None)
        assert refreshed.dub_source == "crunchyroll_rss"
    assert summary["skipped_already_filled"] >= 1


def test_ingest_dry_run_no_writes(app):
    _seed_anime(app)
    with app.app_context():
        before = Episode.query.count()
        summary = ingest_payload(JSON_FIXTURE_LIST, dry_run=True)
        after = Episode.query.count()
    assert before == after
    assert summary["dry_run"] is True
    assert summary["written"] == 0
    assert summary["matched"] >= 3


def test_ingest_skips_missing_episode_number(app):
    _seed_anime(app)
    with app.app_context():
        summary = ingest_payload(JSON_FIXTURE_LIST, dry_run=True)
    assert summary["skipped_no_episode_number"] >= 1


def test_ingest_records_unmatched_titles(app):
    _seed_anime(app)
    with app.app_context():
        summary = ingest_payload(JSON_FIXTURE_LIST, dry_run=True)
    assert summary["unmatched"] >= 1
    assert any(
        "Random" in u["title"] for u in summary["unmatched_titles"]
    )


def test_ingest_is_idempotent_on_clean_writes(app):
    _seed_anime(app)
    with app.app_context():
        first = ingest_payload(JSON_FIXTURE_LIST, dry_run=False)
        # Second run: every row that was filled is now "already filled".
        second = ingest_payload(JSON_FIXTURE_LIST, dry_run=False)
    assert second["written"] == 0
    assert second["skipped_already_filled"] >= first["written"]


def test_ingest_uses_english_title_fallback(app):
    """If the Japanese title doesn't match, fall back to English."""
    with app.app_context():
        anime = Anime(
            anilist_id=3001,
            title="Boku no Hero Academia",
            title_english="My Hero Academia",
            synopsis="",
            year=2016,
            episodes=13,
            studio="Bones",
            image_url="",
            source="MANGA",
            status="RELEASING",
        )
        db.session.add(anime)
        db.session.commit()
        anime_id = anime.id

        # Use an unusual romaji that won't match the Japanese title strongly
        # but English fallback should still catch it.
        payload = json.dumps(
            [
                {
                    "title": "Buko no Heeroo Akademiia",  # nonsense romaji
                    "english": "My Hero Academia",
                    "episodeNumber": 5,
                    "episodeDate": "2026-06-01T12:00:00Z",
                }
            ]
        )
        summary = ingest_payload(payload, dry_run=False)
        ep = (
            Episode.query
            .filter_by(anime_id=anime_id, episode_number=5)
            .first()
        )
        assert ep is not None
        assert ep.dub_source == DUB_SOURCE
    assert summary["written"] == 1


# ─── HTTP layer ──────────────────────────────────────────────────────────────


@responses.activate
def test_fetch_payload_success():
    responses.add(
        responses.GET,
        ANIMESCHEDULE_URL,
        body=JSON_FIXTURE_LIST,
        status=200,
        content_type="application/json",
    )
    payload = fetch_payload()
    assert "Attack on Titan" in payload


@responses.activate
def test_fetch_payload_raises_on_4xx():
    responses.add(responses.GET, ANIMESCHEDULE_URL, status=403)
    with pytest.raises(Exception):
        fetch_payload()


def test_ingest_upgrades_synthetic_estimates(app):
    """Tier 2 (real timetable) must replace Tier 5 (synthetic projection).

    A +8-week estimate blocking a real near-simulcast date left users a
    month-plus wrong (observed live: estimate 2026-08-14 vs timetable
    2026-07-06). Real sources outrank the synthetic seeder — always.
    """
    from datetime import datetime as dt
    from seed_dub_schedule import SYNTHETIC_TAG

    with app.app_context():
        anime = Anime(title="Synthetic Upgrade Show", status="Currently Airing")
        db.session.add(anime)
        db.session.flush()
        db.session.add(Episode(
            anime_id=anime.id, episode_number=1,
            air_date_sub=dt(2026, 6, 1),
            air_date_dub=dt(2026, 8, 14),        # stale +8w estimate
            dub_source=SYNTHETIC_TAG,
        ))
        db.session.commit()
        aid = anime.id

        payload = json.dumps([{
            "title": "Synthetic Upgrade Show",
            "episodeNumber": 1,
            "episodeDate": "2026-07-06T18:00:00Z",
        }])
        summary = ingest_payload(payload, dry_run=False)

        ep = Episode.query.filter_by(anime_id=aid, episode_number=1).first()
        assert ep.dub_source == "animeschedule"
        assert ep.air_date_dub.replace(tzinfo=None) == dt(2026, 7, 6, 18, 0)
    assert summary["written"] == 1
    assert summary["upgraded_synthetic"] == 1
    assert summary["skipped_already_filled"] == 0


def test_ingest_refreshes_own_rows_only_when_date_moves(app):
    """Same-payload re-runs stay idempotent; a moved timetable date updates."""
    from datetime import datetime as dt

    with app.app_context():
        anime = Anime(title="Self Refresh Show", status="Currently Airing")
        db.session.add(anime)
        db.session.flush()
        db.session.commit()
        aid = anime.id

        first = json.dumps([{
            "title": "Self Refresh Show",
            "episodeNumber": 2,
            "episodeDate": "2026-07-06T18:00:00Z",
        }])
        s1 = ingest_payload(first, dry_run=False)
        s2 = ingest_payload(first, dry_run=False)          # unchanged date
        moved = json.dumps([{
            "title": "Self Refresh Show",
            "episodeNumber": 2,
            "episodeDate": "2026-07-08T18:00:00Z",
        }])
        s3 = ingest_payload(moved, dry_run=False)

        ep = Episode.query.filter_by(anime_id=aid, episode_number=2).first()
        assert ep.air_date_dub.replace(tzinfo=None) == dt(2026, 7, 8, 18, 0)
    assert s1["written"] == 1
    assert s2["written"] == 0 and s2["skipped_already_filled"] == 1
    assert s3["written"] == 1


def test_ingest_never_touches_research_or_user_rows(app):
    from datetime import datetime as dt

    with app.app_context():
        for i, src in enumerate(("research", "user:parusan"), start=1):
            anime = Anime(title=f"Protected Source Show {i}",
                          status="Currently Airing")
            db.session.add(anime)
            db.session.flush()
            db.session.add(Episode(
                anime_id=anime.id, episode_number=1,
                air_date_dub=dt(2026, 8, 1), dub_source=src,
            ))
        db.session.commit()

        payload = json.dumps([
            {"title": "Protected Source Show 1", "episodeNumber": 1,
             "episodeDate": "2026-07-06T18:00:00Z"},
            {"title": "Protected Source Show 2", "episodeNumber": 1,
             "episodeDate": "2026-07-06T18:00:00Z"},
        ])
        summary = ingest_payload(payload, dry_run=False)

        kept = [
            Episode.query.join(Anime).filter(
                Anime.title == f"Protected Source Show {i}"
            ).first().dub_source
            for i in (1, 2)
        ]
        assert kept == ["research", "user:parusan"]
    assert summary["written"] == 0
    assert summary["skipped_already_filled"] == 2
