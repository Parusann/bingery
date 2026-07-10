"""Shared Episode/Anime week-window query for the /schedule API and the auditor.

Both `routes/schedule.py::_collect` and `audit_schedule.py` enumerate the same
serving surface through `window_rows_query`, so any eligibility rule added here
(air-date window today, per-track status guards tomorrow) is applied to the
user-facing timeline and to the audit identically — the auditor can never
drift from what the schedule actually serves.
"""

from __future__ import annotations

from datetime import datetime

from models import db, Anime, Episode


def window_rows_query(field, start_naive: datetime, end_naive: datetime):
    """Return the (Episode, Anime) query for one track's air-date window.

    `field` is Episode.air_date_sub or Episode.air_date_dub; the bounds are
    naive-UTC datetimes matching how the columns are stored.
    """
    return (
        db.session.query(Episode, Anime)
        .join(Anime, Anime.id == Episode.anime_id)
        .filter(field >= start_naive)
        .filter(field < end_naive)
    )
