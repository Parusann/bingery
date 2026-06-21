"""Tests for seed_dub_schedule.py learned-lag projection."""
from datetime import datetime, timedelta

from models import db, Anime, Episode
from seed_dub_schedule import _learned_lag_days, SYNTHETIC_TAG, LAG_DAYS, main


def test_learned_lag_days_median():
    assert _learned_lag_days([14, 16]) == 15
    assert _learned_lag_days([10, 20, 21]) == 20
    assert _learned_lag_days([]) is None


def test_seeder_uses_learned_lag_for_partially_dubbed_show():
    # The seeder's main() runs against the global app (`from app import app`),
    # so seed + assert through that same app to share its DB.
    from app import app as seeder_app

    with seeder_app.app_context():
        a = Anime(
            title="Learned Lag Show DUBTEST",
            api_score=9.5,
            status="Currently Airing",
        )
        db.session.add(a)
        db.session.flush()
        # Episode 1 has a REAL dub 21 days after its sub date.
        db.session.add(Episode(
            anime_id=a.id, episode_number=1,
            air_date_sub=datetime(2026, 1, 1),
            air_date_dub=datetime(2026, 1, 22),
            dub_source="crunchyroll_rss",
        ))
        # Episode 2 has only a sub date -> projected at the learned +21 days.
        db.session.add(Episode(
            anime_id=a.id, episode_number=2,
            air_date_sub=datetime(2026, 1, 8),
        ))
        db.session.commit()
        aid = a.id

    main([])

    with seeder_app.app_context():
        ep2 = Episode.query.filter_by(anime_id=aid, episode_number=2).first()
        assert ep2.dub_source == SYNTHETIC_TAG
        assert ep2.air_date_dub == datetime(2026, 1, 8) + timedelta(days=21)
        # The real-source episode is untouched.
        ep1 = Episode.query.filter_by(anime_id=aid, episode_number=1).first()
        assert ep1.dub_source == "crunchyroll_rss"


def test_seeder_falls_back_to_default_lag():
    from app import app as seeder_app

    with seeder_app.app_context():
        a = Anime(
            title="No Dub Data Show DUBTEST",
            api_score=9.4,
            status="Currently Airing",
        )
        db.session.add(a)
        db.session.flush()
        db.session.add(Episode(
            anime_id=a.id, episode_number=1,
            air_date_sub=datetime(2026, 2, 1),
        ))
        db.session.commit()
        aid = a.id

    main([])

    with seeder_app.app_context():
        ep = Episode.query.filter_by(anime_id=aid, episode_number=1).first()
        assert ep.dub_source == SYNTHETIC_TAG
        assert ep.air_date_dub == datetime(2026, 2, 1) + timedelta(days=LAG_DAYS)
