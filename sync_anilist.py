"""
Full-catalog AniList sync script.

Drives a resumable, rate-limited, idempotent sync of the entire AniList anime
catalog by **chunking the query by `seasonYear`** (1960 to current+1). Within
each year, standard page-based pagination — no year has >5000 anime so we
never approach AniList's deep-page-offset cap at 5000. `state.last_page` is
repurposed as "last completed year"; resumes restart from `last_page + 1`.

Wall-clock for the full ~25k-anime catalog: ~10-30 minutes depending on
rate-limit retries.

Known gap: anime with `seasonYear: null` (rare; mostly unscheduled specials)
are not reachable via this query and remain unsynced.

Usage:
    python sync_anilist.py                    # default: --resume
    python sync_anilist.py --full             # start from year=1960
    python sync_anilist.py --resume           # continue from last_year + 1
    python sync_anilist.py --dry-run          # print what would be written
    python sync_anilist.py --max-pages 5      # cap total API calls (testing)
    python sync_anilist.py --since 2026-01-01 # incremental (best-effort)
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Optional


# ─── Rate-limiting between pages ────────────────────────────────────────────
# AniList's documented limit is 90 req/min. We sleep 0.7s between page fetches
# to target ~85 req/min and leave headroom for retry-after on 429s.
PAGE_SLEEP_SECONDS = 0.7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _airing_at_to_dt(airing_at: Optional[int]) -> Optional[datetime]:
    """Convert AniList's epoch-seconds airingAt to a UTC datetime."""
    if airing_at is None:
        return None
    try:
        return datetime.fromtimestamp(int(airing_at), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _upsert_episode(
    anime_id: int,
    episode_number: int,
    air_date_sub: Optional[datetime],
    dry_run: bool = False,
) -> Optional["Episode"]:
    """Upsert one Episode row by (anime_id, episode_number). Returns the row
    (or None in dry-run). Caller is responsible for committing."""
    from models import db, Episode

    if episode_number is None or episode_number <= 0:
        return None

    if dry_run:
        return None

    existing = Episode.query.filter_by(
        anime_id=anime_id, episode_number=episode_number
    ).first()

    if existing:
        if air_date_sub is not None and existing.air_date_sub != air_date_sub:
            existing.air_date_sub = air_date_sub
            if not existing.sub_source:
                existing.sub_source = "anilist"
        return existing

    ep = Episode(
        anime_id=anime_id,
        episode_number=episode_number,
        air_date_sub=air_date_sub,
        sub_source="anilist",
    )
    db.session.add(ep)
    db.session.flush()
    return ep


def process_media_entry(media: dict, dry_run: bool = False) -> dict:
    """
    Upsert one normalized AniList media entry — both the Anime row and any
    Episode rows from its airingSchedule / nextAiringEpisode.

    Returns a small summary dict with counts (useful for tests + logging).
    """
    from models import db
    from utils.anilist import sync_anime_to_db

    summary = {
        "anilist_id": media.get("anilist_id"),
        "title": media.get("title"),
        "anime_created": False,
        "episodes_upserted": 0,
        "dry_run": dry_run,
    }

    if dry_run:
        schedule_nodes = media.get("airing_schedule") or []
        next_airing = media.get("next_airing_episode") or None
        summary["episodes_upserted"] = len(schedule_nodes) + (1 if next_airing else 0)
        return summary

    # 1. Upsert the Anime row (matches by anilist_id, then mal_id).
    anime = sync_anime_to_db(media)
    db.session.flush()  # need anime.id for FK
    summary["anime_id"] = anime.id

    # 2. Upsert episodes from the airingSchedule.
    schedule_nodes = media.get("airing_schedule") or []
    for node in schedule_nodes:
        ep_num = node.get("episode")
        air_dt = _airing_at_to_dt(node.get("airingAt"))
        ep = _upsert_episode(anime.id, ep_num, air_dt, dry_run=False)
        if ep is not None:
            summary["episodes_upserted"] += 1

    # 3. Upsert the nextAiringEpisode (often already covered by the schedule,
    #    but unique constraint handles the dedup).
    next_airing = media.get("next_airing_episode") or None
    if next_airing:
        ep_num = next_airing.get("episode")
        air_dt = _airing_at_to_dt(next_airing.get("airingAt"))
        ep = _upsert_episode(anime.id, ep_num, air_dt, dry_run=False)
        if ep is not None:
            summary["episodes_upserted"] += 1

    return summary


def _format_eta(seconds_remaining: float) -> str:
    if seconds_remaining < 0 or seconds_remaining != seconds_remaining:  # NaN
        return "?h ?m"
    hours = int(seconds_remaining // 3600)
    minutes = int((seconds_remaining % 3600) // 60)
    return f"{hours}h {minutes}m"


DEFAULT_END_YEAR_OFFSET = 1  # how many years past current year to include


def run_sync(
    client,
    start_year: int,
    end_year: int,
    max_pages: Optional[int] = None,
    dry_run: bool = False,
    since: Optional[datetime] = None,
    is_full: bool = False,
    sleep_seconds: float = PAGE_SLEEP_SECONDS,
    log: callable = print,
) -> dict:
    """
    Core sync loop chunking by seasonYear.

    Outer loop walks years from `start_year` to `end_year` inclusive. Inner
    loop paginates within each year (standard page-based, never deep enough
    to hit the 5000-offset wall since no year has >5000 anime). After
    completing all pages for a year, advances state.last_page (repurposed as
    "last completed year"). Pulled out into its own function so tests can
    drive it with a mocked client and no real sleeps.

    `max_pages` means "max total API calls" across all years (CLI compat).

    Returns a summary dict.
    """
    from models import db, get_or_create_sync_state

    state = get_or_create_sync_state()
    state.status = "running"
    state.last_run_at = _utcnow()
    state.error_message = None
    if not dry_run:
        db.session.commit()

    pages_processed = 0
    media_processed = 0
    episodes_processed = 0
    last_page_info: Optional[dict] = None
    last_year_seen: Optional[int] = None
    started = time.time()

    try:
        for year in range(start_year, end_year + 1):
            last_year_seen = year
            page = 1
            while True:
                if max_pages is not None and pages_processed >= max_pages:
                    log(f"Reached --max-pages={max_pages}, stopping.")
                    # Don't advance last_page; we didn't finish this year.
                    raise StopIteration

                if pages_processed > 0:
                    time.sleep(sleep_seconds)

                result = client.fetch_catalog_page(season_year=year, page=page)
                page_info = result["page_info"]
                last_page_info = page_info
                media_list = result["media"]

                page_media_count = 0
                page_episode_count = 0
                for media in media_list:
                    # Optional --since: skip if AniList updatedAt is older
                    # than the cutoff. Best-effort: AniList's fragment doesn't
                    # always expose updatedAt.
                    if since is not None:
                        raw_updated = (
                            media.get("updatedAt") or media.get("updated_at")
                        )
                        if raw_updated:
                            try:
                                up_dt = datetime.fromtimestamp(
                                    int(raw_updated), tz=timezone.utc
                                )
                                if up_dt < since:
                                    continue
                            except (TypeError, ValueError, OverflowError):
                                pass

                    summary = process_media_entry(media, dry_run=dry_run)
                    page_media_count += 1
                    page_episode_count += summary["episodes_upserted"]

                if not dry_run:
                    state.total_synced = (
                        (state.total_synced or 0) + page_media_count
                    )
                    db.session.commit()

                pages_processed += 1
                media_processed += page_media_count
                episodes_processed += page_episode_count

                # Progress every 10 API calls.
                if pages_processed % 10 == 0:
                    elapsed = time.time() - started
                    rate = media_processed / elapsed if elapsed > 0 else 0
                    # ETA based on remaining years assuming similar density.
                    years_done = year - start_year
                    years_left = max(0, end_year - year)
                    avg_per_year = (
                        media_processed / max(1, years_done) if years_done else 0
                    )
                    items_left = years_left * avg_per_year
                    eta_seconds = items_left / rate if rate > 0 else 0
                    log(
                        f"Year {year} page {page}, "
                        f"~{media_processed} anime synced, "
                        f"~{episodes_processed} episodes, "
                        f"ETA {_format_eta(eta_seconds)}"
                    )

                if not page_info.get("hasNextPage", False):
                    break

                page += 1

            # Year complete — advance state.last_page (= last completed year).
            if not dry_run:
                state.last_page = year
                db.session.commit()

    except StopIteration:
        # max_pages cap hit. Don't mark sync as failed.
        pass
    except KeyboardInterrupt:
        if not dry_run:
            state.status = "idle"
            db.session.commit()
        log("Interrupted by user (Ctrl-C). State saved.")
        raise
    except Exception as exc:
        if not dry_run:
            state.status = "error"
            state.error_message = f"{type(exc).__name__}: {exc}"
            db.session.commit()
        log(f"ERROR: {state.error_message if not dry_run else exc}")
        raise

    # Success path.
    if not dry_run:
        state.status = "idle"
        state.error_message = None
        if is_full:
            state.last_full_at = _utcnow()
        db.session.commit()

    return {
        "ok": True,
        "pages_processed": pages_processed,
        "media_processed": media_processed,
        "episodes_processed": episodes_processed,
        "last_year_completed": (
            (last_year_seen - 1) if last_year_seen and last_year_seen < end_year
            else last_year_seen
        ),
        "page_info": last_page_info,
        "dry_run": dry_run,
    }


# AniList MediaFormat enum values most likely to host `seasonYear: null` orphans.
ORPHAN_FORMATS = ("SPECIAL", "OVA", "ONA", "MUSIC", "TV_SHORT")
# Per AniList docs: deep page-based pagination caps out at offset 5000
# (page 100 with perPage=50). Bail at that page to avoid a server-side error.
MAX_PAGES_PER_FORMAT = 100


def run_format_sync(
    client,
    media_format: str,
    *,
    max_pages: Optional[int] = None,
    dry_run: bool = False,
    sleep_seconds: float = PAGE_SLEEP_SECONDS,
    log: callable = print,
) -> dict:
    """Page through every anime of one AniList MediaFormat and upsert it.

    Counterpart to `run_sync` (which chunks by seasonYear). Used to reach
    entries with `seasonYear: null` — typically older SPECIAL / OVA / ONA /
    MUSIC entries that the year-chunker can never see. Idempotent: upserts
    by anilist_id so re-running just refreshes existing rows.

    Stops when AniList reports no more pages OR we hit the 5000-offset cap
    (page 100). Honors `--max-pages` for testing.
    """
    pages_processed = 0
    media_processed = 0
    episodes_processed = 0
    last_page_info: Optional[dict] = None
    started = time.time()

    page = 1
    while True:
        if max_pages is not None and pages_processed >= max_pages:
            log(f"Reached --max-pages={max_pages}, stopping.")
            break
        if page > MAX_PAGES_PER_FORMAT:
            log(
                f"Reached AniList deep-page cap (page {MAX_PAGES_PER_FORMAT}) "
                f"for format={media_format}. Stopping to avoid 5000-offset error."
            )
            break

        if pages_processed > 0:
            time.sleep(sleep_seconds)

        result = client.fetch_catalog_page_by_format(
            media_format=media_format, page=page
        )
        page_info = result["page_info"]
        last_page_info = page_info
        media_list = result["media"]

        page_media_count = 0
        page_episode_count = 0
        for media in media_list:
            summary = process_media_entry(media, dry_run=dry_run)
            page_media_count += 1
            page_episode_count += summary["episodes_upserted"]

        pages_processed += 1
        media_processed += page_media_count
        episodes_processed += page_episode_count

        if pages_processed % 10 == 0:
            elapsed = time.time() - started
            rate = media_processed / elapsed if elapsed > 0 else 0
            log(
                f"format={media_format} page {page}, "
                f"~{media_processed} anime processed, "
                f"~{episodes_processed} episodes, "
                f"rate {rate:.1f}/s"
            )

        if not page_info.get("hasNextPage", False):
            break
        page += 1

    return {
        "ok": True,
        "format": media_format,
        "pages_processed": pages_processed,
        "media_processed": media_processed,
        "episodes_processed": episodes_processed,
        "page_info": last_page_info,
        "dry_run": dry_run,
    }


def run_airing_sync(
    client,
    *,
    max_pages: Optional[int] = None,
    dry_run: bool = False,
    sleep_seconds: float = PAGE_SLEEP_SECONDS,
    log: callable = print,
) -> dict:
    """Page through currently-RELEASING anime and upsert each.

    Keeps airing / next-episode data fresh for the schedule without a full
    catalog walk. Idempotent (upserts by anilist_id). Honors --max-pages.
    """
    pages_processed = 0
    media_processed = 0
    episodes_processed = 0
    last_page_info: Optional[dict] = None
    started = time.time()

    page = 1
    while True:
        if max_pages is not None and pages_processed >= max_pages:
            log(f"Reached --max-pages={max_pages}, stopping.")
            break
        if page > MAX_PAGES_PER_FORMAT:
            log(
                f"Reached AniList deep-page cap (page {MAX_PAGES_PER_FORMAT}). "
                "Stopping to avoid 5000-offset error."
            )
            break

        if pages_processed > 0:
            time.sleep(sleep_seconds)

        result = client.fetch_airing_page(page=page)
        page_info = result["page_info"]
        last_page_info = page_info

        for media in result["media"]:
            summary = process_media_entry(media, dry_run=dry_run)
            media_processed += 1
            episodes_processed += summary["episodes_upserted"]

        pages_processed += 1

        if pages_processed % 10 == 0:
            elapsed = time.time() - started
            rate = media_processed / elapsed if elapsed > 0 else 0
            log(
                f"airing page {page}, ~{media_processed} anime, "
                f"~{episodes_processed} episodes, rate {rate:.1f}/s"
            )

        if not page_info.get("hasNextPage", False):
            break
        page += 1

    return {
        "ok": True,
        "pages_processed": pages_processed,
        "media_processed": media_processed,
        "episodes_processed": episodes_processed,
        "page_info": last_page_info,
        "dry_run": dry_run,
    }


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full-catalog AniList sync for Bingery."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--full",
        action="store_true",
        help="Start from id_greater=0 (re-scans entire catalog from scratch).",
    )
    mode.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue from the max anilist_id currently in the DB (default). "
            "Idempotent: rows already present are upserted, not duplicated."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written; do not commit to the DB.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help=(
            "Cap how many fetch iterations this run processes (useful for "
            "testing). One iteration = up to 50 anime."
        ),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help=(
            "Incremental: skip anime whose AniList updatedAt is older than "
            "YYYY-MM-DD. Best-effort; AniList's fragment doesn't always "
            "expose updatedAt."
        ),
    )
    parser.add_argument(
        "--format",
        type=str,
        default=None,
        dest="media_format",
        metavar="FMT",
        help=(
            "Orphan-catcher mode: paginate by AniList MediaFormat instead of "
            "seasonYear. Use to reach entries with seasonYear=null (mostly "
            "SPECIAL / OVA / ONA / MUSIC / TV_SHORT). Repeatable via "
            "--all-orphan-formats."
        ),
    )
    parser.add_argument(
        "--all-orphan-formats",
        action="store_true",
        help=(
            "Run orphan-catcher mode across every format likely to host "
            f"seasonYear=null entries: {', '.join(ORPHAN_FORMATS)}."
        ),
    )

    parser.add_argument(
        "--airing",
        action="store_true",
        help=(
            "Refresh currently-RELEASING anime (airing / next-episode data) for "
            "the schedule. Cheap and bounded; intended to run daily."
        ),
    )

    args = parser.parse_args(argv)

    # Default behavior with no mode flag: resume.
    if not args.full and not args.resume:
        args.resume = True

    since_dt: Optional[datetime] = None
    if args.since:
        try:
            since_dt = datetime.strptime(args.since, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            print(f"ERROR: --since must be YYYY-MM-DD (got {args.since!r})")
            return 2

    if args.max_pages is not None and args.max_pages <= 0:
        print(f"--max-pages={args.max_pages}: nothing to do, exiting cleanly.")
        return 0

    # Initialize Flask app context (the standard pattern used elsewhere).
    from app import create_app
    from models import get_or_create_sync_state
    from utils.anilist import AniListClient

    app = create_app()
    ctx = app.app_context()
    ctx.push()

    try:
        # ── Airing-refresh branch: --airing ─────────────────────────────────
        if args.airing:
            from utils.anilist import AniListClient as _AniListClient
            summary = run_airing_sync(
                _AniListClient(), max_pages=args.max_pages or 10, dry_run=args.dry_run
            )
            print(
                f"--airing done: pages={summary['pages_processed']} "
                f"anime={summary['media_processed']} dry_run={args.dry_run}"
            )
            return 0

        # ── Orphan-catcher branch: --format / --all-orphan-formats ──────────
        if args.media_format or args.all_orphan_formats:
            if args.media_format and args.all_orphan_formats:
                print(
                    "ERROR: --format and --all-orphan-formats are mutually exclusive."
                )
                return 2
            formats = (
                [args.media_format] if args.media_format else list(ORPHAN_FORMATS)
            )
            from utils.anilist import AniListClient as _AniListClient
            client = _AniListClient()
            total_media = 0
            total_pages = 0
            for fmt in formats:
                print(f"Starting orphan-catcher: format={fmt}, dry_run={args.dry_run}")
                try:
                    summary = run_format_sync(
                        client,
                        media_format=fmt,
                        max_pages=args.max_pages,
                        dry_run=args.dry_run,
                    )
                except KeyboardInterrupt:
                    return 130
                except Exception as exc:
                    print(f"FATAL ({fmt}): {type(exc).__name__}: {exc}")
                    return 1
                print(
                    f"  done. format={fmt} pages={summary['pages_processed']} "
                    f"anime={summary['media_processed']} "
                    f"episodes={summary['episodes_processed']} "
                    f"dry_run={summary['dry_run']}"
                )
                total_media += summary["media_processed"]
                total_pages += summary["pages_processed"]
            print(
                f"All formats done. total_pages={total_pages} "
                f"total_anime={total_media} dry_run={args.dry_run}"
            )
            return 0

        # AniList's catalog starts circa 1917 (silent-era specials). We start
        # from 1960 — the practical "modern anime" floor; anything earlier is
        # vanishingly rare and AniList coverage is spotty there.
        FIRST_YEAR = 1960
        end_year = datetime.now(timezone.utc).year + DEFAULT_END_YEAR_OFFSET

        if args.full:
            start_year = FIRST_YEAR
        else:
            # Resume from the year AFTER the last completed year. state.last_page
            # is repurposed as "last completed year".
            state = get_or_create_sync_state()
            last_done = state.last_page or 0
            if last_done < FIRST_YEAR:
                start_year = FIRST_YEAR
            else:
                start_year = last_done + 1

        if start_year > end_year:
            print(
                f"Already synced through {start_year - 1} (end_year={end_year}). "
                "Use --full to re-sync from scratch."
            )
            return 0

        print(
            f"Starting AniList sync. years={start_year}-{end_year}, "
            f"dry_run={args.dry_run}"
        )

        client = AniListClient()
        try:
            summary = run_sync(
                client,
                start_year=start_year,
                end_year=end_year,
                max_pages=args.max_pages,
                dry_run=args.dry_run,
                since=since_dt,
                is_full=args.full,
            )
        except KeyboardInterrupt:
            return 130
        except Exception as exc:
            print(f"FATAL: {type(exc).__name__}: {exc}")
            return 1

        print(
            f"Done. API_calls={summary['pages_processed']}, "
            f"anime={summary['media_processed']}, "
            f"episodes={summary['episodes_processed']}, "
            f"last_year_completed={summary['last_year_completed']}, "
            f"dry_run={summary['dry_run']}"
        )
        return 0
    finally:
        ctx.pop()


if __name__ == "__main__":
    sys.exit(main())
