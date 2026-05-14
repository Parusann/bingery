"""CLI entry for the Crunchyroll RSS dub ingester (Plan 4 Tier 1).

Usage:
    python sync_dub_crunchyroll.py                    # live fetch, write to DB
    python sync_dub_crunchyroll.py --dry-run          # parse + match, no writes
    python sync_dub_crunchyroll.py --since 2026-05-01 # skip older entries
    python sync_dub_crunchyroll.py --url <file:///>   # override RSS URL (testing)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest Crunchyroll RSS feed into Episode.air_date_dub.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and match but do not write to the DB.",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Skip entries whose pubDate is before this YYYY-MM-DD.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Override the RSS URL (useful for testing against a fixture).",
    )
    args = parser.parse_args(argv)

    since_dt: Optional[datetime] = None
    if args.since:
        try:
            since_dt = datetime.strptime(args.since, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            print(f"ERROR: --since must be YYYY-MM-DD (got {args.since!r})")
            return 2

    from app import create_app
    from utils.dub_sources.crunchyroll import (
        CR_RSS_URL,
        fetch_feed,
        ingest_feed,
    )

    app = create_app()
    ctx = app.app_context()
    ctx.push()
    try:
        url = args.url or CR_RSS_URL
        print(f"Fetching {url} ...")
        try:
            xml = fetch_feed(url)
        except Exception as exc:
            print(f"FATAL fetch error: {type(exc).__name__}: {exc}")
            return 1

        summary = ingest_feed(xml, dry_run=args.dry_run, since=since_dt)
        print(
            f"Done. parsed={summary['parsed']} matched={summary['matched']} "
            f"written={summary['written']} unmatched={summary['unmatched']} "
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
