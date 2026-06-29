"""Generic dub-date ingest for structured rows.

Accepts pre-normalized rows — each with an explicit air_date plus either an
anilist_id (exact match) or a title (fuzzy match) and an episode_number — and
fills Episode.air_date_dub. These are treated as *real* dates (default
dub_source="research"): they upgrade NULL or synthetic rows and are themselves
preserved by the synthetic seeder. Other real sources (crunchyroll_rss /
animeschedule / user:*) are only overwritten with overwrite=True.

Powers POST /api/admin/ingest-dub-dates — the ingestion side of the monthly
"research" fallback that fills dub dates AnimeSchedule.net still misses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from utils.dub_sources.crunchyroll import best_match, MATCH_THRESHOLD

# Real dub sources we won't silently clobber unless overwrite=True. Mirrors the
# synthetic seeder's protection so authoritative feeds win over a research guess.
_PROTECTED_REAL = {"crunchyroll_rss", "animeschedule"}


def _parse_iso(value) -> Optional[datetime]:
    """Parse an ISO-8601 string (or pass through a datetime) to UTC-aware.

    Returns None on junk. A bare "Z" suffix is normalised for Python < 3.11.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ingest_dub_rows(
    rows: Iterable[dict],
    *,
    dub_source: str = "research",
    overwrite: bool = False,
    threshold: float = MATCH_THRESHOLD,
) -> dict:
    """Fill Episode.air_date_dub from structured rows. Returns a summary dict.

    Row keys:
        anilist_id     int  — preferred exact match on Anime.anilist_id
        title          str  — fuzzy fallback when anilist_id is absent/unmatched
        episode_number int  — required
        air_date       str|datetime — ISO-8601 (UTC assumed if naive); required

    Tiering: NULL and synthetic dub dates are filled freely; crunchyroll_rss,
    animeschedule and user:* dates are preserved unless overwrite=True.
    """
    from collections import namedtuple
    from models import db, Anime, Episode

    summary = {
        "parsed": 0,
        "matched": 0,
        "written": 0,
        "skipped_protected": 0,
        "unmatched": 0,
        "skipped_bad_row": 0,
        "dub_source": dub_source,
        "overwrite": overwrite,
        "unmatched_titles": [],
    }

    _AnimeCand = namedtuple("_AnimeCand", ["id", "title", "title_english"])
    _candidates: Optional[list] = None

    def candidates() -> list:
        # Built lazily and once — only if a row needs a title-based match.
        nonlocal _candidates
        if _candidates is None:
            _candidates = [
                _AnimeCand(r.id, r.title, r.title_english)
                for r in db.session.query(
                    Anime.id, Anime.title, Anime.title_english
                ).all()
            ]
        return _candidates

    for row in rows or []:
        if not isinstance(row, dict):
            summary["skipped_bad_row"] += 1
            continue
        summary["parsed"] += 1

        ep_num = _coerce_int(row.get("episode_number"))
        air = _parse_iso(row.get("air_date"))
        if ep_num is None or air is None:
            summary["skipped_bad_row"] += 1
            continue

        anime = None
        anilist_id = _coerce_int(row.get("anilist_id"))
        if anilist_id is not None:
            anime = (
                db.session.query(Anime).filter_by(anilist_id=anilist_id).first()
            )
        if anime is None:
            title = row.get("title")
            if isinstance(title, str) and title.strip():
                cand, score = best_match(title, candidates())
                if cand is not None and score >= threshold:
                    anime = db.session.get(Anime, cand.id)
        if anime is None:
            summary["unmatched"] += 1
            title = row.get("title")
            summary["unmatched_titles"].append(
                {
                    "title": title if isinstance(title, str) else None,
                    "anilist_id": anilist_id,
                }
            )
            continue
        summary["matched"] += 1

        ep = (
            Episode.query
            .filter_by(anime_id=anime.id, episode_number=ep_num)
            .first()
        )
        if ep is None:
            ep = Episode(anime_id=anime.id, episode_number=ep_num)
            db.session.add(ep)

        existing = ep.dub_source or ""
        protected = existing in _PROTECTED_REAL or existing.startswith("user:")
        if ep.air_date_dub is not None and protected and not overwrite:
            summary["skipped_protected"] += 1
            continue

        ep.air_date_dub = air
        ep.dub_source = dub_source
        summary["written"] += 1

    db.session.commit()
    return summary
