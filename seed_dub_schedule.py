"""Seed synthetic dub release dates for the /schedule page.

Why: real dub sources (Crunchyroll RSS, AnimeSchedule.net) don't always
list *future* episodes of a show that's already dubbed. For those shows we
extend the schedule by projecting each remaining sub episode forward by the
show's own learned sub->dub lag (the median of its real dub data points).
Shows with no real dub evidence are left untouched — we don't invent a dub
date for a title that may have no English dub at all.

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

# Catalog spellings that mean the show's (sub) run is over. Used by the
# ghost-prune below and by the serving guards in utils/schedule_window.py.
FINISHED_STATUSES = ("Finished Airing", "Completed", "Cancelled")

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
    parser.add_argument("--prune-ghosts", action="store_true",
                        help=(
                            "Remove fabricated synthetic rows and exit: projections "
                            "for finished/cancelled shows with no real dub evidence, "
                            "and projections numbered past the show's episode count. "
                            "Attended maintenance — not run by the daily sync."
                        ))
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

        # ── Prune-ghosts path ────────────────────────────────────────
        if args.prune_ghosts:
            from sqlalchemy import or_ as sa_or, update as sa_update

            preserve = sa_or(
                Episode.dub_source.in_(tuple(_REAL_DUB_SOURCES)),
                Episode.dub_source.like("user:%"),
            )
            synth_anime = {
                aid for (aid,) in db.session.query(Episode.anime_id)
                .filter(Episode.dub_source == SYNTHETIC_TAG).distinct()
            }
            evidence_anime = {
                aid for (aid,) in db.session.query(Episode.anime_id)
                .filter(Episode.air_date_dub.isnot(None), preserve).distinct()
            }
            finished_anime = {
                aid for (aid,) in db.session.query(Anime.id)
                .filter(Anime.id.in_(synth_anime),
                        Anime.status.in_(FINISHED_STATUSES))
            }
            # A: finished shows with zero real dub activity — the projection
            # was never legitimate (the dub may not exist at all).
            targets = sorted(finished_anime - evidence_anime)
            wiped_finished = 0
            if targets and not args.dry_run:
                wiped_finished = (
                    Episode.query
                    .filter(Episode.anime_id.in_(targets),
                            Episode.dub_source == SYNTHETIC_TAG)
                    .update({Episode.air_date_dub: None,
                             Episode.dub_source: None},
                            synchronize_session=False)
                )
            elif targets:
                wiped_finished = (
                    db.session.query(Episode.id)
                    .filter(Episode.anime_id.in_(targets),
                            Episode.dub_source == SYNTHETIC_TAG)
                    .count()
                )
            # B: projections numbered past the catalog's own episode count —
            # those episodes cannot exist on any track.
            counts = dict(
                db.session.query(Anime.id, Anime.episodes)
                .filter(Anime.id.in_(synth_anime),
                        Anime.episodes.isnot(None), Anime.episodes > 0)
            )
            wiped_overrun = 0
            for aid, total in counts.items():
                q = Episode.query.filter(
                    Episode.anime_id == aid,
                    Episode.dub_source == SYNTHETIC_TAG,
                    Episode.episode_number > total,
                )
                if args.dry_run:
                    wiped_overrun += q.count()
                else:
                    wiped_overrun += q.update(
                        {Episode.air_date_dub: None, Episode.dub_source: None},
                        synchronize_session=False,
                    )
            if not args.dry_run:
                db.session.commit()
            print(
                f"prune-ghosts{' (dry-run)' if args.dry_run else ''}: "
                f"cleared {wiped_finished} synthetic rows across "
                f"{len(targets)} finished evidence-less shows; "
                f"cleared {wiped_overrun} rows numbered past the finale"
            )
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

        # Learn each show's real sub->dub gap (sparse query — only episodes
        # that already carry a real dub date are hydrated, so this stays well
        # under the memory budget the bulk path was protecting). A show earns a
        # synthetic projection ONLY if it has real dub evidence: we no longer
        # invent dub dates for shows with no dub at all. That over-projection
        # produced bogus dubs for never-dubbed long-runners (Sazae-san,
        # Doraemon), a far-behind "dub" for shows like One Piece, and a
        # duplicate estimate on every current-season catalog entry whose real
        # date matched a sibling record. Real dub dates come from
        # AnimeSchedule/Crunchyroll; the synthetic seed only *extends* an
        # already-dubbed show's future episodes at its own observed lag.
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
        dubbed_ids = list(learned.keys())

        candidate_count = (
            db.session.query(sa_func.count(Episode.id))
            .filter(*eligible_clauses, Episode.anime_id.in_(dubbed_ids))
            .scalar()
        ) if dubbed_ids else 0
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
            f"candidate episodes: {candidate_count} across {len(dubbed_ids)} "
            f"dubbed shows (real-source rows preserved: {preserved_count})"
        )

        if args.dry_run:
            print(
                f"dry-run: would set air_date_dub on {candidate_count} episodes "
                f"across {len(dubbed_ids)} dubbed shows "
                f"(preserved {preserved_count} real-source rows)"
            )
            return 0

        n_set = 0
        # Shows with real dub data: project their remaining episodes at the
        # show's own observed lag. Shows with no dub evidence are skipped.
        # Never project past the catalog's own episode count — a projection
        # for episode N+1 of an N-episode show fabricates a date for an
        # episode that cannot exist.
        episode_totals = dict(
            db.session.query(Anime.id, Anime.episodes)
            .filter(Anime.id.in_(dubbed_ids))
        ) if dubbed_ids else {}
        for aid, lag in learned.items():
            per_show_clauses = list(eligible_clauses)
            total = episode_totals.get(aid)
            if total and total > 0:
                per_show_clauses.append(
                    or_(
                        Episode.episode_number.is_(None),
                        Episode.episode_number <= total,
                    )
                )
            res = db.session.execute(
                update(Episode)
                .where(*per_show_clauses, Episode.anime_id == aid)
                .values(
                    air_date_dub=sa_func.datetime(
                        Episode.air_date_sub, f"+{lag} days"
                    ),
                    dub_source=SYNTHETIC_TAG,
                )
                .execution_options(synchronize_session=False)
            )
            n_set += res.rowcount or 0
        db.session.commit()
        print(
            f"wrote air_date_dub on {n_set} episodes "
            f"({len(learned)} dubbed shows at learned lag, "
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
