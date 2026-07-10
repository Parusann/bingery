"""CLI entry for the AnimeSchedule.net dub ingester (Plan 4 Tier 2).

Usage:
    python sync_dub_animeschedule.py            # live fetch, fill NULL air_date_dub
    python sync_dub_animeschedule.py --dry-run  # parse + match, no writes
    python sync_dub_animeschedule.py --url <...>  # override URL (testing)
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest AnimeSchedule.net dub timetable into Episode.air_date_dub (Tier 2).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and match but do not write to the DB.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Override the timetable URL (useful for testing).",
    )
    args = parser.parse_args(argv)

    from app import create_app
    from utils.dub_sources.animeschedule import (
        ANIMESCHEDULE_API_KEY_ENV,
        ANIMESCHEDULE_URL,
        fetch_payload,
        ingest_payload,
    )

    import os

    if not args.url and not os.environ.get(ANIMESCHEDULE_API_KEY_ENV):
        # Fail loudly and distinctly: this is a credentials problem, not a
        # transient fetch error. Without the key the live endpoint 401s,
        # no real dub dates sync, and the synthetic seeder's estimates are
        # all the schedule has.
        print(
            f"TIER DARK: {ANIMESCHEDULE_API_KEY_ENV} is not set.\n"
            "  Real dub dates will NOT sync; the schedule will show "
            "synthetic estimates only.\n"
            "  Provision a token at https://animeschedule.net/ (account "
            "settings) and set it in the runtime environment."
        )
        return 2

    app = create_app()
    ctx = app.app_context()
    ctx.push()
    try:
        url = args.url or ANIMESCHEDULE_URL
        print(f"Fetching {url} ...")
        try:
            payload = fetch_payload(url)
        except Exception as exc:
            print(f"FATAL fetch error: {type(exc).__name__}: {exc}")
            return 1

        summary = ingest_payload(payload, dry_run=args.dry_run)
        print(
            f"Done. parsed={summary['parsed']} matched={summary['matched']} "
            f"written={summary['written']} "
            f"upgraded_synthetic={summary['upgraded_synthetic']} "
            f"already_filled={summary['skipped_already_filled']} "
            f"unmatched={summary['unmatched']} "
            f"skipped_no_ep={summary['skipped_no_episode_number']} "
            f"dry_run={summary['dry_run']}"
        )
        if summary["unmatched_titles"]:
            shown = min(5, len(summary["unmatched_titles"]))
            print(f"First {shown} unmatched (of {len(summary['unmatched_titles'])}):")
            for u in summary["unmatched_titles"][:shown]:
                print(f"  - {u['title']!r} (best score: {u['score']:.1f})")
        return 0
    finally:
        ctx.pop()


if __name__ == "__main__":
    sys.exit(main())
