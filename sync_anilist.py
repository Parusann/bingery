"""
Full-catalog AniList sync script.

Drives a resumable, rate-limited, idempotent sync of the entire AniList anime
catalog into Bingery's database. Each page (50 anime) takes ~0.7s + DB write
time; a full sync of ~25k anime takes ~5h wall-clock.

Usage:
    python sync_anilist.py                    # default: --resume
    python sync_anilist.py --full             # start from page 1
    python sync_anilist.py --resume           # continue from last_page + 1
    python sync_anilist.py --dry-run          # print what would be written
    python sync_anilist.py --max-pages 5      # cap for testing
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


def run_sync(
    client,
    start_page: int,
    max_pages: Optional[int] = None,
    dry_run: bool = False,
    since: Optional[datetime] = None,
    is_full: bool = False,
    sleep_seconds: float = PAGE_SLEEP_SECONDS,
    log: callable = print,
) -> dict:
    """
    Core sync loop. Pulled out into its own function so tests can drive it
    with a mocked client and no real sleeps.

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
    started = time.time()

    current_page = start_page
    try:
        while True:
            if max_pages is not None and pages_processed >= max_pages:
                log(f"Reached --max-pages={max_pages}, stopping.")
                break

            if pages_processed > 0:
                time.sleep(sleep_seconds)

            result = client.fetch_catalog_page(current_page)
            page_info = result["page_info"]
            last_page_info = page_info
            media_list = result["media"]

            page_media_count = 0
            page_episode_count = 0
            for media in media_list:
                # Optional --since: skip if AniList updatedAt is older than the
                # cutoff. AniList doesn't always expose updatedAt in our
                # fragment, so this is best-effort and may be a no-op.
                if since is not None:
                    raw_updated = media.get("updatedAt") or media.get("updated_at")
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
                state.last_page = current_page
                state.total_synced = (state.total_synced or 0) + page_media_count
                db.session.commit()

            pages_processed += 1
            media_processed += page_media_count
            episodes_processed += page_episode_count

            # Progress every 10 pages, plus on the final page.
            if pages_processed % 10 == 0 or not page_info.get("hasNextPage", False):
                elapsed = time.time() - started
                last_page_num = page_info.get("lastPage") or 0
                pages_left = max(0, last_page_num - current_page)
                if max_pages is not None:
                    pages_left = min(pages_left, max_pages - pages_processed)
                rate = pages_processed / elapsed if elapsed > 0 else 0
                eta_seconds = pages_left / rate if rate > 0 else 0
                log(
                    f"Page {current_page}/{last_page_num}, "
                    f"~{media_processed} anime synced, "
                    f"~{episodes_processed} episodes, "
                    f"ETA {_format_eta(eta_seconds)}"
                )

            if not page_info.get("hasNextPage", False):
                break

            current_page += 1

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
            "last_page": current_page if pages_processed > 0 else (start_page - 1),
            "page_info": last_page_info,
            "dry_run": dry_run,
        }

    except KeyboardInterrupt:
        if not dry_run:
            state.status = "idle"
            db.session.commit()
        log("Interrupted by user (Ctrl-C). State saved.")
        raise

    except Exception as exc:  # network errors, 4xx/5xx, etc.
        if not dry_run:
            state.status = "error"
            state.error_message = f"{type(exc).__name__}: {exc}"
            db.session.commit()
        log(f"ERROR: {state.error_message if not dry_run else exc}")
        raise


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Full-catalog AniList sync for Bingery."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--full",
        action="store_true",
        help="Start from page 1 (overwrites existing sync state's last_page).",
    )
    mode.add_argument(
        "--resume",
        action="store_true",
        help="Continue from AniListSyncState.last_page + 1 (default).",
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
        help="Cap how many pages this run processes (useful for testing).",
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
        state = get_or_create_sync_state()
        if args.full:
            start_page = 1
        else:
            start_page = (state.last_page or 0) + 1

        print(f"Starting AniList sync. start_page={start_page}, dry_run={args.dry_run}")

        client = AniListClient()
        try:
            summary = run_sync(
                client,
                start_page=start_page,
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
            f"Done. Pages={summary['pages_processed']}, "
            f"anime={summary['media_processed']}, "
            f"episodes={summary['episodes_processed']}, "
            f"last_page={summary['last_page']}, dry_run={summary['dry_run']}"
        )
        return 0
    finally:
        ctx.pop()


if __name__ == "__main__":
    sys.exit(main())
