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
from datetime import timedelta

SYNTHETIC_TAG = "synthetic_lag_8w"
LAG_DAYS = 56


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change; write nothing.")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe synthetic rows (dub_source=%(default)r) and exit." % {"default": SYNTHETIC_TAG})
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing air_date_dub even from real sources. Off by default.")
    parser.add_argument("--top", type=int, default=400,
                        help="How many top-rated currently-airing anime to include (by api_score). Default 400.")
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

        # ── Selection: top-N currently-airing by score ───────────────
        # The DB uses the AniList/MAL phrasing "Currently Airing". We also
        # accept "Airing" as a courtesy in case the seed ever changes.
        airing_q = (
            db.session.query(Anime.id)
            .filter(Anime.status.in_(("Currently Airing", "Airing")))
            .filter(Anime.api_score.isnot(None))
            .order_by(Anime.api_score.desc())
            .limit(args.top)
        )
        anime_ids = [row[0] for row in airing_q.all()]
        print(f"selected {len(anime_ids)} currently-airing anime (top by score)")

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
        for ep in eps:
            ep.air_date_dub = ep.air_date_sub + lag
            ep.dub_source = SYNTHETIC_TAG
            n_set += 1

        if args.dry_run:
            db.session.rollback()
            print(f"dry-run: would set air_date_dub on {n_set} episodes")
            return 0

        db.session.commit()
        print(f"wrote air_date_dub on {n_set} episodes (lag={LAG_DAYS}d, tag={SYNTHETIC_TAG!r})")

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
