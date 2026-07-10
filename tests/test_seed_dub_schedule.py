"""Tests for seed_dub_schedule.py learned-lag projection."""
from datetime import datetime, timedelta

from models import db, Anime, Episode
from seed_dub_schedule import _learned_lag_days, SYNTHETIC_TAG, main


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


def test_seeder_skips_shows_with_no_dub_evidence():
    # A currently-airing show with only sub dates and NO real dub data must
    # NOT get a synthetic dub date. We no longer invent dubs for shows that
    # may have no dub at all (never-dubbed long-runners, far-behind dubs).
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
        assert ep.air_date_dub is None
        assert ep.dub_source is None


def test_seeder_never_projects_past_episode_count():
    # Episode rows numbered beyond Anime.episodes are ghosts (season splits,
    # stale schedules); the seeder must not fabricate dub dates for them.
    from app import app as seeder_app

    with seeder_app.app_context():
        a = Anime(
            title="Overrun Guard Show DUBTEST",
            api_score=9.3,
            status="Currently Airing",
            episodes=2,
        )
        db.session.add(a)
        db.session.flush()
        db.session.add(Episode(
            anime_id=a.id, episode_number=1,
            air_date_sub=datetime(2026, 3, 1),
            air_date_dub=datetime(2026, 3, 22),
            dub_source="crunchyroll_rss",
        ))
        db.session.add(Episode(
            anime_id=a.id, episode_number=2,
            air_date_sub=datetime(2026, 3, 8),
        ))
        db.session.add(Episode(
            anime_id=a.id, episode_number=3,  # beyond the 2-episode finale
            air_date_sub=datetime(2026, 3, 15),
        ))
        db.session.commit()
        aid = a.id

    main([])

    with seeder_app.app_context():
        ep2 = Episode.query.filter_by(anime_id=aid, episode_number=2).first()
        assert ep2.dub_source == SYNTHETIC_TAG  # within the finale: projected
        ep3 = Episode.query.filter_by(anime_id=aid, episode_number=3).first()
        assert ep3.air_date_dub is None         # past the finale: never
        assert ep3.dub_source is None


def test_prune_ghosts_clears_finished_evidenceless_and_overrun():
    from app import app as seeder_app

    with seeder_app.app_context():
        # Finished show, synthetic rows, zero real dub activity → pruned.
        ghost = Anime(title="Prune Ghost DUBTEST", api_score=9.0,
                      status="Finished Airing")
        # Finished show WITH real dub evidence → trailing estimate survives.
        trailing = Anime(title="Prune Trailing DUBTEST", api_score=9.1,
                         status="Finished Airing")
        # Airing show, synthetic overrun row past the finale → pruned.
        overrun = Anime(title="Prune Overrun DUBTEST", api_score=9.2,
                        status="Currently Airing", episodes=5)
        db.session.add_all([ghost, trailing, overrun])
        db.session.flush()
        db.session.add(Episode(
            anime_id=ghost.id, episode_number=1,
            air_date_sub=datetime(2026, 4, 1),
            air_date_dub=datetime(2026, 5, 27), dub_source=SYNTHETIC_TAG,
        ))
        db.session.add(Episode(
            anime_id=trailing.id, episode_number=1,
            air_date_sub=datetime(2026, 4, 1),
            air_date_dub=datetime(2026, 4, 22), dub_source="crunchyroll_rss",
        ))
        db.session.add(Episode(
            anime_id=trailing.id, episode_number=2,
            air_date_sub=datetime(2026, 4, 8),
            air_date_dub=datetime(2026, 4, 29), dub_source=SYNTHETIC_TAG,
        ))
        db.session.add(Episode(
            anime_id=overrun.id, episode_number=6,
            air_date_sub=datetime(2026, 4, 15),
            air_date_dub=datetime(2026, 6, 10), dub_source=SYNTHETIC_TAG,
        ))
        db.session.commit()
        ids = (ghost.id, trailing.id, overrun.id)

    rc = main(["--prune-ghosts"])
    assert rc == 0

    with seeder_app.app_context():
        g = Episode.query.filter_by(anime_id=ids[0], episode_number=1).first()
        assert g.air_date_dub is None and g.dub_source is None
        t1 = Episode.query.filter_by(anime_id=ids[1], episode_number=1).first()
        assert t1.dub_source == "crunchyroll_rss"
        t2 = Episode.query.filter_by(anime_id=ids[1], episode_number=2).first()
        assert t2.dub_source == SYNTHETIC_TAG   # evidenced estimate survives
        o = Episode.query.filter_by(anime_id=ids[2], episode_number=6).first()
        assert o.air_date_dub is None and o.dub_source is None


def test_prune_ghosts_dry_run_writes_nothing():
    from app import app as seeder_app

    with seeder_app.app_context():
        a = Anime(title="Prune DryRun DUBTEST", api_score=8.9,
                  status="Finished Airing")
        db.session.add(a)
        db.session.flush()
        db.session.add(Episode(
            anime_id=a.id, episode_number=1,
            air_date_sub=datetime(2026, 4, 1),
            air_date_dub=datetime(2026, 5, 27), dub_source=SYNTHETIC_TAG,
        ))
        db.session.commit()
        aid = a.id

    rc = main(["--prune-ghosts", "--dry-run"])
    assert rc == 0

    with seeder_app.app_context():
        ep = Episode.query.filter_by(anime_id=aid, episode_number=1).first()
        assert ep.dub_source == SYNTHETIC_TAG  # untouched
