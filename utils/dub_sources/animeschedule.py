"""AnimeSchedule.net dub-release ingester (Plan 4 Tier 2).

Fetches a JSON timetable from AnimeSchedule.net, fuzzy-matches show titles
against the local Anime catalog, and fills Episode.air_date_dub **only when
the field is currently NULL** (Tier 1 — Crunchyroll RSS — has precedence).

dub_source is set to "animeschedule" for rows this ingester writes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

import requests

from utils.dub_sources.crunchyroll import best_match  # reuse fuzzy matcher

ANIMESCHEDULE_URL = "https://animeschedule.net/api/v3/timetables/dub"
ANIMESCHEDULE_API_KEY_ENV = "ANIMESCHEDULE_API_KEY"
DUB_SOURCE = "animeschedule"
MATCH_THRESHOLD = 80.0
FETCH_TIMEOUT = 30
USER_AGENT = "bingery-dub-sync/1.0"


@dataclass(frozen=True)
class AnimeScheduleEntry:
    """Normalized representation of one row in the timetable response."""

    title: str
    english_title: Optional[str]
    episode_number: Optional[int]
    air_date: datetime


@dataclass
class IngestSummary:
    """Result of one ingest_payload run."""

    parsed: int = 0
    matched: int = 0
    written: int = 0
    skipped_already_filled: int = 0
    unmatched: int = 0
    skipped_no_episode_number: int = 0
    dry_run: bool = False
    unmatched_titles: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "parsed": self.parsed,
            "matched": self.matched,
            "written": self.written,
            "skipped_already_filled": self.skipped_already_filled,
            "unmatched": self.unmatched,
            "skipped_no_episode_number": self.skipped_no_episode_number,
            "dry_run": self.dry_run,
            "unmatched_titles": list(self.unmatched_titles),
        }


# ─── Fetching ────────────────────────────────────────────────────────────────


def fetch_payload(
    url: str = ANIMESCHEDULE_URL,
    *,
    timeout: int = FETCH_TIMEOUT,
    api_key: Optional[str] = None,
) -> str:
    """GET the timetable and return raw JSON text. Raises on HTTP error.

    AnimeSchedule.net's v3 API requires a Bearer token. Pass it via `api_key`
    or set the ANIMESCHEDULE_API_KEY env var. Without a key the live endpoint
    returns 401; tests don't require a key (they mock the HTTP layer).
    """
    headers = {"User-Agent": USER_AGENT}
    token = api_key or os.environ.get(ANIMESCHEDULE_API_KEY_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    return resp.text


# ─── Parsing ─────────────────────────────────────────────────────────────────


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 date string. Returns UTC-aware datetime."""
    if not s:
        return None
    # Python's fromisoformat accepts "...+00:00" but not the legacy "Z" suffix
    # until 3.11+. Normalize defensively.
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _pick(d: dict, *keys: str) -> Optional[object]:
    """Return the first non-empty value among the given keys."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None


def _coerce_int(v: Optional[object]) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_payload(json_text: str) -> list[AnimeScheduleEntry]:
    """Parse the timetable JSON into normalized entries.

    Accepts either a top-level list or a {"results": [...]} envelope.
    Picks the most common field names defensively so minor schema changes
    don't blow the parser up.
    """
    raw = json.loads(json_text)
    if isinstance(raw, dict):
        rows = raw.get("results") or raw.get("data") or []
    elif isinstance(raw, list):
        rows = raw
    else:
        return []

    out: list[AnimeScheduleEntry] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _pick(row, "title", "name") or ""
        english_title = _pick(row, "english", "english_title", "title_english")
        if not isinstance(title, str) or not title.strip():
            continue
        if english_title is not None and not isinstance(english_title, str):
            english_title = None
        episode_number = _coerce_int(
            _pick(row, "episodeNumber", "episode_number", "episode")
        )
        air_iso = _pick(
            row,
            "episodeDate",
            "episode_date",
            "airDate",
            "air_date",
            "airingDate",
        )
        if not isinstance(air_iso, str):
            continue
        air_dt = _parse_iso_date(air_iso)
        if air_dt is None:
            continue
        out.append(
            AnimeScheduleEntry(
                title=title.strip(),
                english_title=english_title.strip() if english_title else None,
                episode_number=episode_number,
                air_date=air_dt,
            )
        )
    return out


# ─── Top-level ingest ────────────────────────────────────────────────────────


def ingest_payload(
    json_text: str,
    *,
    dry_run: bool = False,
    threshold: float = MATCH_THRESHOLD,
) -> dict:
    """Parse JSON, fuzzy-match, fill Episode.air_date_dub only where NULL.

    Tier 2 semantics: never overwrite an existing air_date_dub. The summary
    reports how many gaps were filled vs already-populated.
    """
    from models import db, Anime, Episode

    summary = IngestSummary(dry_run=dry_run)
    entries = parse_payload(json_text)
    summary.parsed = len(entries)
    if not entries:
        return summary.to_dict()

    candidates = Anime.query.all()
    for entry in entries:
        if entry.episode_number is None:
            summary.skipped_no_episode_number += 1
            continue
        # Try Japanese title first, then English fallback.
        anime, score = best_match(entry.title, candidates)
        if (anime is None or score < threshold) and entry.english_title:
            anime, score = best_match(entry.english_title, candidates)
        if anime is None or score < threshold:
            summary.unmatched += 1
            summary.unmatched_titles.append(
                {"title": entry.title, "score": round(score, 1)}
            )
            continue
        summary.matched += 1

        ep = (
            Episode.query
            .filter_by(anime_id=anime.id, episode_number=entry.episode_number)
            .first()
        )
        if ep is not None and ep.air_date_dub is not None:
            summary.skipped_already_filled += 1
            continue
        if dry_run:
            continue
        if ep is None:
            ep = Episode(
                anime_id=anime.id, episode_number=entry.episode_number
            )
            db.session.add(ep)
        ep.air_date_dub = entry.air_date
        ep.dub_source = DUB_SOURCE
        summary.written += 1

    if not dry_run:
        db.session.commit()
    return summary.to_dict()


def ingest_payload_from_iterable(
    rows: Iterable[dict], *, dry_run: bool = False
) -> dict:
    """Convenience: ingest from an in-memory list of row dicts."""
    return ingest_payload(json.dumps(list(rows)), dry_run=dry_run)
