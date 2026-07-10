"""Schedule auditor — verify every entry the weekly schedule serves.

Enumerates the exact serving surface of `/api/schedule/week` (via the shared
`utils.schedule_window.window_rows_query`) for a configurable window, checks
every sub and dub date against independent sources (AniList GraphQL, official
MyAnimeList API v2 with keyless Jikan fallback, AnimeSchedule.net timetables,
Crunchyroll RSS, and optional attended web-research claims), classifies each
entry (CONFIRMED / MISMATCH / ESTIMATED / UNVERIFIABLE), flags evidence-backed
leaks per track, and writes a machine-readable JSON report plus a
human-readable Markdown summary.

Read-only: this script NEVER writes to the database. Corrections go through
the existing precedence machinery (`POST /api/admin/ingest-dub-dates`,
`sync_anilist.sync_ids`) in attended runs.

Usage:
    python audit_schedule.py --weeks 3 --tag baseline
    python audit_schedule.py --offline            # no network, smoke/enumeration
    python audit_schedule.py --fail-on-thresholds # CI gate (report-only, exit 1)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from utils.schedule_audit import (
    AuditReport,
    EntryAudit,
    TierHealth,
    canonical_db_status,
    classify_entry,
    evaluate_thresholds,
)

from seed_dub_schedule import SYNTHETIC_TAG

DEFAULT_OUT_DIR = os.path.join("reports", "schedule-audit")


def sunday_of(dt: datetime) -> datetime:
    """UTC midnight of the Sunday on/before dt (the schedule's week anchor)."""
    dt = dt.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return dt - timedelta(days=(dt.weekday() + 1) % 7)


def enumerate_entries(week_start: datetime, weeks: int, lang: str = "both"):
    """Collect (entries, anime_records) for the audit window.

    Uses the same shared query the API route uses, over [week_start,
    week_start + weeks*7d) in UTC. Returns EntryAudit skeletons (not yet
    classified) plus light-weight anime records for the source clients.
    """
    from models import Episode
    from utils.schedule_window import window_rows_query

    # The route queries a ±1 day margin around the visible window because
    # timezone bucketing can pull margin rows into a viewer's week. Audit the
    # same superset so no served row escapes enumeration.
    anchor = week_start.astimezone(timezone.utc).replace(tzinfo=None)
    start_naive = anchor - timedelta(days=1)
    end_naive = anchor + timedelta(days=7 * weeks + 1)

    tracks = []
    if lang in ("sub", "both"):
        tracks.append(("sub", Episode.air_date_sub))
    if lang in ("dub", "both"):
        tracks.append(("dub", Episode.air_date_dub))

    entries: list[EntryAudit] = []
    anime_seen: dict[int, dict] = {}
    for track, field in tracks:
        for episode, anime in window_rows_query(field, start_naive, end_naive).all():
            raw = getattr(episode, field.key)
            our_date = raw.replace(tzinfo=timezone.utc) if raw.tzinfo is None else raw
            entries.append(
                EntryAudit(
                    anime_id=anime.id,
                    anime_title=anime.title_english or anime.title,
                    anilist_id=anime.anilist_id,
                    mal_id=anime.mal_id,
                    episode_id=episode.id,
                    episode_number=episode.episode_number,
                    track=track,
                    our_date=our_date,
                    our_source=(
                        episode.dub_source if track == "dub" else episode.sub_source
                    ),
                    synthetic=(
                        track == "dub" and (episode.dub_source or "") == SYNTHETIC_TAG
                    ),
                    db_status=canonical_db_status(anime.status),
                )
            )
            if anime.id not in anime_seen:
                anime_seen[anime.id] = {
                    "id": anime.id,
                    "anilist_id": anime.anilist_id,
                    "mal_id": anime.mal_id,
                    "title": anime.title,
                    "title_english": anime.title_english,
                    "status": anime.status,
                    "year": anime.year,
                    "season": anime.season,
                }
    return entries, list(anime_seen.values())


def run_audit(
    *,
    week_start: datetime,
    weeks: int = 2,
    lang: str = "both",
    max_anime: int | None = None,
    sources=None,
    now: datetime | None = None,
) -> AuditReport:
    """Run one audit and return the report. `sources` is injectable for tests;
    None means the default live tier stack; [] means offline."""
    window_end = week_start + timedelta(days=7 * weeks)
    report = AuditReport(
        window_start=week_start,
        window_end=window_end,
        generated_at=now or datetime.now(timezone.utc),
    )

    entries, anime_records = enumerate_entries(week_start, weeks, lang)

    if max_anime is not None and len(anime_records) > max_anime:
        kept_ids = {a["id"] for a in anime_records[:max_anime]}
        dropped = len(anime_records) - max_anime
        report.notes.append(
            f"COVERAGE CAP: --max-anime={max_anime} dropped {dropped} of "
            f"{len(anime_records)} window anime from verification"
        )
        anime_records = [a for a in anime_records if a["id"] in kept_ids]
        entries = [e for e in entries if e.anime_id in kept_ids]

    if sources is None:
        from utils.audit_sources import default_sources

        sources, http = default_sources(
            cache_path=os.environ.get("AUDIT_CACHE_FILE"),
            research_file=os.environ.get("AUDIT_RESEARCH_FILE"),
        )
    else:
        http = None

    claims_by_anime: dict[int, list] = {}
    if sources:
        for source in sources:
            claims, health = source.collect(anime_records, week_start, window_end)
            for anime_id, source_claims in claims.items():
                claims_by_anime.setdefault(anime_id, []).extend(source_claims)
            report.tiers.append(health)
    else:
        report.notes.append("OFFLINE RUN: no sources queried")
        for name in ("anilist", "myanimelist", "animeschedule",
                     "crunchyroll_rss", "web_research"):
            report.tiers.append(
                TierHealth(name=name, state="skipped", detail="offline run")
            )

    for entry in entries:
        classify_entry(
            entry, claims_by_anime.get(entry.anime_id, []), now=report.generated_at
        )
        report.entries.append(entry)

    if http is not None:
        http.cache.save()

    needs_research = sorted(
        {
            e.anime_title
            for e in report.entries
            if e.classification in ("MISMATCH", "UNVERIFIABLE") and not e.synthetic
        }
    )
    if needs_research:
        report.notes.append(
            "NEEDS RESEARCH (structured sources silent or disagreeing): "
            + ", ".join(needs_research[:40])
        )
    return report


def main(argv=None) -> int:
    # Windows consoles default to cp1252, which cannot encode the report's
    # arrows/dashes; never let a summary print kill an otherwise-good run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", help="Sunday anchor YYYY-MM-DD (default: this week)")
    parser.add_argument("--weeks", type=int, default=2)
    parser.add_argument("--lang", choices=("sub", "dub", "both"), default="both")
    parser.add_argument("--max-anime", type=int, default=None)
    parser.add_argument("--offline", action="store_true",
                        help="no network; enumeration + synthetic labeling only")
    parser.add_argument("--cache", help="JSON response-cache file (dev re-runs)")
    parser.add_argument("--research-file",
                        help="attended web-research claims JSON (never set in CI)")
    parser.add_argument("--out", default=DEFAULT_OUT_DIR)
    parser.add_argument("--tag", default=None,
                        help="report filename tag (default: UTC timestamp)")
    parser.add_argument("--fail-on-thresholds", action="store_true")
    parser.add_argument("--max-mismatch", type=int, default=5)
    parser.add_argument("--max-synthetic-frac", type=float, default=0.6)
    parser.add_argument("--max-leaks", type=int, default=0)
    args = parser.parse_args(argv)

    if args.cache:
        os.environ["AUDIT_CACHE_FILE"] = args.cache
    if args.research_file:
        os.environ["AUDIT_RESEARCH_FILE"] = args.research_file

    if args.week:
        requested = datetime.strptime(args.week, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        week_start = sunday_of(requested)
        if week_start != requested:
            print(f"note: --week {args.week} is not a Sunday; "
                  f"snapped to {week_start.date()}")
    else:
        week_start = sunday_of(datetime.now(timezone.utc))

    from app import create_app

    app = create_app()
    with app.app_context():
        report = run_audit(
            week_start=week_start,
            weeks=args.weeks,
            lang=args.lang,
            max_anime=args.max_anime,
            sources=[] if args.offline else None,
        )

    os.makedirs(args.out, exist_ok=True)
    tag = args.tag or report.generated_at.strftime("%Y%m%dT%H%M%SZ")
    json_path = os.path.join(args.out, f"{tag}-audit.json")
    md_path = os.path.join(args.out, f"{tag}-audit.md")
    with open(json_path, "w", encoding="utf-8") as fh:
        fh.write(report.to_json())
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(report.summary_markdown())

    print(report.summary_markdown())
    print(f"JSON report: {json_path}")
    print(f"Markdown summary: {md_path}")

    breaches = evaluate_thresholds(
        report.totals(),
        max_mismatch=args.max_mismatch,
        max_synthetic_fraction=args.max_synthetic_frac,
        max_leaks=args.max_leaks,
    )
    if breaches:
        print("\nTHRESHOLD BREACHES:")
        for b in breaches:
            print(f"  - {b}")
        if args.fail_on_thresholds:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
