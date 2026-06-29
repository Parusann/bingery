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
# to clobber authoritative data from RSS, AnimeSchedule, the research
# fallback, or user reports. Real sources also seed each show's learned lag.
_REAL_DUB_SOURCES = {"crunchyroll_rss", "animeschedule", "research"}


def _learned_lag_days(deltas: list[int]) -> int | None:
    """Median sub->dub gap (days) from a show's real dub data points, or None."""
    from statistics import median

    return int(median(deltas)) if deltas else None


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
        # Bulk SQL UPDATE so the seed never hydrates rows into Python
        # memory. Fly's 256MB shared machine was OOM-killing the ORM
        # version once the cohort grew past ~250 anime; this stays
        # well under that budget regardless of cohort size.
        from sqlalchemy import update, or_, func as sa_func

        preserve_clause = or_(
            Episode.dub_source.in_(tuple(_REAL_DUB_SOURCES)),
            Episode.dub_source.like("user:%"),
        )
        # Projectable = no dub yet (NULL) or an existing synthetic projection.
        # NULL-safe: `~preserve_clause` would evaluate to NULL (→ excluded) for
        # the sub-only episodes we most need to fill.
        eligible_clauses = [
            Episode.anime_id.in_(anime_ids),
            Episode.air_date_sub.isnot(None),
            or_(Episode.dub_source.is_(None), Episode.dub_source == SYNTHETIC_TAG),
        ]
        if not args.overwrite:
            eligible_clauses.append(Episode.air_date_dub.is_(None))

        candidate_count = (
            db.session.query(sa_func.count(Episode.id))
            .filter(*eligible_clauses)
            .scalar()
        )
        preserved_count = (
            db.session.query(sa_func.count(Episode.id))
            .filter(
                Episode.anime_id.in_(anime_ids),
                Episode.air_date_sub.isnot(None),
                preserve_clause,
            )
            .scalar()
        )
        print(
            f"candidate episodes: {candidate_count} "
            f"(real-source rows preserved: {preserved_count})"
        )

        if args.dry_run:
            print(
                f"dry-run: would set air_date_dub on {candidate_count} episodes "
                f"(preserved {preserved_count} real-source rows)"
            )
            return 0

        # Learn each show's real sub->dub gap (sparse query — only episodes that
        # already carry a real dub date are hydrated, so this stays well under
        # the memory budget the bulk path was protecting).
        from collections import defaultdict
        real_rows = (
            db.session.query(
                Episode.anime_id, Episode.air_date_sub, Episode.air_date_dub
            )
            .filter(
                Episode.anime_id.in_(anime_ids),
                Episode.air_date_sub.isnot(None),
                Episode.air_date_dub.isnot(None),
                preserve_clause,
            )
            .all()
        )
        gaps = defaultdict(list)
        for aid, sub, dub in real_rows:
            gaps[aid].append((dub - sub).days)
        learned = {
            aid: lag
            for aid, ds in gaps.items()
            if (lag := _learned_lag_days(ds)) is not None
        }

        n_set = 0
        # Shows with real dub data: project at their own observed lag.
        for aid, lag in learned.items():
            res = db.session.execute(
                update(Episode)
                .where(*eligible_clauses, Episode.anime_id == aid)
                .values(
                    air_date_dub=sa_func.datetime(
                        Episode.air_date_sub, f"+{lag} days"
                    ),
                    dub_source=SYNTHETIC_TAG,
                )
                .execution_options(synchronize_session=False)
            )
            n_set += res.rowcount or 0
        # Everyone else: the flat default lag.
        default_ids = [aid for aid in anime_ids if aid not in learned]
        if default_ids:
            res = db.session.execute(
                update(Episode)
                .where(*eligible_clauses, Episode.anime_id.in_(default_ids))
                .values(
                    air_date_dub=sa_func.datetime(
                        Episode.air_date_sub, f"+{LAG_DAYS} days"
                    ),
                    dub_source=SYNTHETIC_TAG,
                )
                .execution_options(synchronize_session=False)
            )
            n_set += res.rowcount or 0
        db.session.commit()
        print(
            f"wrote air_date_dub on {n_set} episodes "
            f"({len(learned)} shows at learned lag, rest at {LAG_DAYS}d default, "
            f"tag={SYNTHETIC_TAG!r}); preserved {preserved_count} real rows"
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
