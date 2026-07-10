"""Shared Episode/Anime week-window query for the /schedule API and the auditor.

Both `routes/schedule.py::_collect` and `audit_schedule.py` enumerate through
`window_rows_query`, so any eligibility rule added here is applied to the
user-facing timeline and to the audit identically. The two callers differ
only by design: the route additionally applies the NSFW filter and buckets
by viewer-local date inside its ±1-day query margin, while the auditor
audits the full margin-inclusive superset (every row any viewer could see).

Ghost guards (per track, evidence-conservative):

* Episode-count bound — an episode numbered beyond the catalog's own
  `Anime.episodes` cannot exist on any track (old rows survive AniList
  season splits; the seeder used to project past the finale).
* Sub track — a future-dated sub episode of a show whose status is
  finished/cancelled never airs; serving it is the "completed-anime leak".
  Past episodes are this week's history and always stay.
* Dub track — dubs outlive subs, so a finished sub does NOT invalidate dub
  rows: real-source dub dates (Crunchyroll/AnimeSchedule/research/user
  reports) are always served, and synthetic projections are served while
  the show is airing or when the show has real dub evidence (the seeder's
  own legitimacy contract). What gets dropped is exactly the fabrication:
  a future synthetic projection for a finished show that has never shown
  any real dub activity.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import aliased

from models import db, Anime, Episode
from seed_dub_schedule import SYNTHETIC_TAG, _REAL_DUB_SOURCES

# Status spellings that mean "this show's (sub) run is over". The catalog
# uses the MAL phrasing; "Completed" appears in older seeds.
FINISHED_STATUSES = ("Finished Airing", "Completed", "Cancelled")


def window_rows_query(field, start_naive: datetime, end_naive: datetime,
                      *, now: datetime | None = None):
    """Return the (Episode, Anime) query for one track's air-date window.

    `field` is Episode.air_date_sub or Episode.air_date_dub; the bounds are
    naive-UTC datetimes matching how the columns are stored. `now` is
    injectable for tests; rows dated at/before it are history and are never
    ghost-filtered.
    """
    if now is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

    query = (
        db.session.query(Episode, Anime)
        .join(Anime, Anime.id == Episode.anime_id)
        .filter(field >= start_naive)
        .filter(field < end_naive)
        # Episode-count bound: rows past the known finale are ghosts.
        .filter(
            or_(
                Anime.episodes.is_(None),
                Anime.episodes <= 0,
                Episode.episode_number.is_(None),
                Episode.episode_number <= Anime.episodes,
            )
        )
    )

    show_is_over = Anime.status.in_(FINISHED_STATUSES)

    if field.key == "air_date_dub":
        evidence_ep = aliased(Episode)
        has_real_dub_evidence = (
            db.session.query(evidence_ep.id)
            .filter(
                evidence_ep.anime_id == Episode.anime_id,
                evidence_ep.air_date_dub.isnot(None),
                or_(
                    evidence_ep.dub_source.in_(tuple(_REAL_DUB_SOURCES)),
                    evidence_ep.dub_source.like("user:%"),
                ),
            )
            .exists()
        )
        query = query.filter(
            or_(
                field <= now,                          # history
                ~show_is_over,                         # show still airing
                Episode.dub_source.is_(None),          # unknown provenance —
                Episode.dub_source != SYNTHETIC_TAG,   # …or a real source
                has_real_dub_evidence,                 # evidenced estimate
            )
        )
    else:
        query = query.filter(or_(field <= now, ~show_is_over))

    return query
