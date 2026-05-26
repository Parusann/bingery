"""Seed synthetic dub release dates for the /schedule page.

Why: the real dub data sources (Crunchyroll RSS, AnimeSchedule.net) cover
only a sliver of titles and the AnimeSchedule key is currently 401-ing,
so the /schedule "dub" tab shows nothing. For the demo we synthesize a
realistic dub schedule by projecting every sub episode of a top-rated
currently-airing anime forward by 56 days (8 weeks — the typical
Crunchyroll/Funi simulcast lag).

The script is idempotent: episodes that already have an air_date_dub
are left alone unless --overwrite is passed.

Usage:
    python seed_dub_schedule.py            # write synthetic dubs
    python seed_dub_schedule.py --dry-run  # report counts only
    python seed_dub_schedule.py --reset    # wipe synthetic rows, then exit
    python seed_dub_schedule.py --top 500  # change anime cohort size
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

SYNTHETIC_TAG = "synthetic_lag_8w"
LAG_DAYS = 56
DEFAULT_RECENT_WINDOW_DAYS = 90

# Real dub sources we never overwrite from the synthetic projector, even
# when --overwrite is passed. The synthetic seed exists to fill gaps, not
# to clobber authoritative data from RSS, AnimeSchedule, or user reports.
_REAL_DUB_SOURCES = {"crunchyroll_rss", "animeschedule"}


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change; write nothing.")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe synthetic rows (dub_source=%(default)r) and exit." % {"default": SYNTHETIC_TAG})
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing air_date_dub even from real sources. Off by default.")
    parser.add_argument("--top", type=int, default=400,
                        help="How many top-rated airing anime to include (by api_score). Default 400.")
    parser.add_argument("--recent-window-days", type=int, default=DEFAULT_RECENT_WINDOW_DAYS,
                        help=(
                            "Also include anime that have at least one sub episode airing "
                            "within +/- this many days of today, regardless of Anime.status. "
                            "Catches shows the catalog has misclassified (default %(default)d). "
                            "Pass 0 to require Anime.status='Currently Airing'."
                        ))
    args = parser.parse_args(argv)

    from app import app
    from models import db, Anime, Episode

    with app.app_context():
        # ── Reset path ───────────────────────────────────────────────
        if args.reset:
            wiped = (
                Episode.query
                .filter(Episode.dub_source == SYNTHETIC_TAG)
                .update(
                    {Episode.air_date_dub: None, Episode.dub_source: None},
                    synchronize_session=False,
                )
            )
            db.session.commit()
            print(f"reset: cleared {wiped} synthetic dub rows")
            return 0

        # ── Selection: top-N airing-or-recently-airing by score ────
        # The DB uses the AniList/MAL phrasing "Currently Airing". We also
        # accept "Airing" as a courtesy in case the seed ever changes.
        # In addition, when --recent-window-days > 0 we include any anime
        # with a sub episode in a +/- window centered on today — this picks
        # up shows whose Anime.status drifted (often "Finished Airing" or
        # "Not Yet Aired") but which are still releasing in the real world.
        from sqlalchemy import or_, exists
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        clauses = [Anime.status.in_(("Currently Airing", "Airing"))]
        if args.recent_window_days and args.recent_window_days > 0:
            win_start = now - timedelta(days=args.recent_window_days)
            win_end = now + timedelta(days=args.recent_window_days)
            has_window_sub = exists().where(
                (Episode.anime_id == Anime.id)
                & (Episode.air_date_sub >= win_start)
                & (Episode.air_date_sub < win_end)
            )
            clauses.append(has_window_sub)

        airing_q = (
            db.session.query(Anime.id)
            .filter(or_(*clauses))
            .filter(Anime.api_score.isnot(None))
            .order_by(Anime.api_score.desc())
            .limit(args.top)
        )
        anime_ids = [row[0] for row in airing_q.all()]
        print(
            f"selected {len(anime_ids)} airing-or-recent anime "
            f"(top by score, +/-{args.recent_window_days}d window)"
        )

        if not anime_ids:
            print("no airing anime found — aborting")
            return 1

        # ── Episode update plan ──────────────────────────────────────
        eps_q = (
            Episode.query
            .filter(Episode.anime_id.in_(anime_ids))
            .filter(Episode.air_date_sub.isnot(None))
        )
        if not args.overwrite:
            eps_q = eps_q.filter(Episode.air_date_dub.is_(None))
        eps = eps_q.all()
        print(f"candidate episodes: {len(eps)}")

        lag = timedelta(days=LAG_DAYS)
        n_set = 0
        n_skipped_real = 0
        for ep in eps:
            # Never clobber real dub data from RSS / AnimeSchedule / user reports,
            # even with --overwrite. The synthetic seed fills gaps; it doesn't
            # outrank an authoritative source.
            if ep.dub_source in _REAL_DUB_SOURCES or (
                ep.dub_source and ep.dub_source.startswith("user:")
            ):
                n_skipped_real += 1
                continue
            ep.air_date_dub = ep.air_date_sub + lag
            ep.dub_source = SYNTHETIC_TAG
            n_set += 1

        if args.dry_run:
            db.session.rollback()
            print(
                f"dry-run: would set air_date_dub on {n_set} episodes "
                f"(skipped {n_skipped_real} with real dub sources)"
            )
            return 0

        db.session.commit()
        print(
            f"wrote air_date_dub on {n_set} episodes (lag={LAG_DAYS}d, tag={SYNTHETIC_TAG!r}); "
            f"preserved {n_skipped_real} real dub-source rows"
        )

        # ── Verification ────────────────────────────────────────────
        from sqlalchemy import func
        total_with_dub = (
            db.session.query(func.count(Episode.id))
            .filter(Episode.air_date_dub.isnot(None))
            .scalar()
        )
        next_14 = (
            db.session.query(func.count(Episode.id))
            .filter(Episode.air_date_dub.isnot(None))
            .filter(Episode.air_date_dub > func.datetime("now"))
            .filter(Episode.air_date_dub < func.datetime("now", "+14 days"))
            .scalar()
        )
        print(f"verify: total episodes w/ dub date = {total_with_dub}; in next 14 days = {next_14}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
