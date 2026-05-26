"""Quick read-only audit of the Episode table — run on prod via fly ssh.

Reports:
- Total episode count
- Sub / dub coverage (rows with non-NULL air date)
- Source breakdown for each lang
- Episodes in the next 7 days for each lang
- Count of currently-airing anime
"""

from datetime import datetime, timedelta, timezone

from app import app
from models import db, Episode, Anime
from sqlalchemy import func


def main() -> None:
    with app.app_context():
        total = Episode.query.count()
        with_sub = Episode.query.filter(Episode.air_date_sub.isnot(None)).count()
        with_dub = Episode.query.filter(Episode.air_date_dub.isnot(None)).count()
        print("=== TOTALS ===")
        print(f"  episodes:       {total}")
        print(f"  with sub date:  {with_sub}")
        print(f"  with dub date:  {with_dub}")

        print("=== SUB SOURCES ===")
        rows = (
            db.session.query(Episode.sub_source, func.count(Episode.id))
            .filter(Episode.air_date_sub.isnot(None))
            .group_by(Episode.sub_source)
            .all()
        )
        for src, cnt in rows:
            print(f"  {src!r:<28} {cnt}")

        print("=== DUB SOURCES ===")
        rows = (
            db.session.query(Episode.dub_source, func.count(Episode.id))
            .filter(Episode.air_date_dub.isnot(None))
            .group_by(Episode.dub_source)
            .all()
        )
        for src, cnt in rows:
            print(f"  {src!r:<28} {cnt}")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        wk_end = now + timedelta(days=7)
        print("=== NEXT 7 DAYS (UTC) ===")
        print(
            "  sub episodes:   "
            + str(
                Episode.query.filter(
                    Episode.air_date_sub >= now, Episode.air_date_sub < wk_end
                ).count()
            )
        )
        print(
            "  dub episodes:   "
            + str(
                Episode.query.filter(
                    Episode.air_date_dub >= now, Episode.air_date_dub < wk_end
                ).count()
            )
        )

        airing = (
            db.session.query(func.count(Anime.id))
            .filter(Anime.status.in_(["Currently Airing", "Airing"]))
            .scalar()
        )
        print("=== AIRING ANIME ===")
        print(f"  currently airing: {airing}")


if __name__ == "__main__":
    main()
