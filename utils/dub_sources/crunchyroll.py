"""Crunchyroll RSS dub-release ingester (Plan 4 Tier 1).

Parses Crunchyroll's public RSS feed, fuzzy-matches each entry's show title
against the local Anime catalog, and writes Episode.air_date_dub rows with
dub_source = "crunchyroll_rss".

Idempotent: re-runs upsert by (anime_id, episode_number) — they don't create
duplicate Episode rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Iterable, Optional
from xml.etree import ElementTree as ET

import requests

CR_RSS_URL = "https://feeds.feedburner.com/crunchyroll/rss"
DUB_SOURCE = "crunchyroll_rss"
MATCH_THRESHOLD = 80.0  # Token-set ratio % required to accept a match.
FETCH_TIMEOUT = 30
USER_AGENT = "bingery-dub-sync/1.0"

# Match "Episode 12", "Ep 12", "Ep. 12", "EP#12", etc.
EPISODE_RE = re.compile(
    r"(?:^|[\s\-–:])(?:episode|ep)\.?\s*#?\s*(\d+)\b",
    re.IGNORECASE,
)
# Strip trailing season/part/cour markers before comparing show titles.
SEASON_SUFFIX_RE = re.compile(
    r"\s*(?:season\s*\d+|s\d+|part\s*\d+|cour\s*\d+)\s*$",
    re.IGNORECASE,
)

# Parse a season number from a title (default 1 when none present). Used by
# best_match to keep a later-season feed from collapsing onto the base/S1 row.
SEASON_NUM_RE = re.compile(
    r"\b(?:season|part|cour)\s*(\d+)\b"
    r"|\b(\d+)(?:st|nd|rd|th)\s+season\b"
    r"|\bs(\d+)\b",
    re.IGNORECASE,
)
# How much to demote a candidate whose season differs from the feed's.
SEASON_MISMATCH_PENALTY = 35.0


def _parse_season(title: str) -> int:
    if not title:
        return 1
    m = SEASON_NUM_RE.search(title)
    if not m:
        return 1
    num = m.group(1) or m.group(2) or m.group(3)
    try:
        return int(num)
    except (TypeError, ValueError):
        return 1


@dataclass(frozen=True)
class CrunchyrollEntry:
    """Normalized representation of one <item> in the RSS feed."""

    raw_title: str
    show_title: str
    episode_number: Optional[int]
    pub_date: datetime


@dataclass
class IngestSummary:
    """Result of one ingest_feed run."""

    parsed: int = 0
    matched: int = 0
    written: int = 0
    unmatched: int = 0
    skipped_no_episode_number: int = 0
    dry_run: bool = False
    unmatched_titles: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "parsed": self.parsed,
            "matched": self.matched,
            "written": self.written,
            "unmatched": self.unmatched,
            "skipped_no_episode_number": self.skipped_no_episode_number,
            "dry_run": self.dry_run,
            "unmatched_titles": list(self.unmatched_titles),
        }


# ─── Fetching ────────────────────────────────────────────────────────────────


def fetch_feed(url: str = CR_RSS_URL, *, timeout: int = FETCH_TIMEOUT) -> str:
    """GET the RSS feed and return raw XML text. Raises on HTTP error."""
    resp = requests.get(
        url, timeout=timeout, headers={"User-Agent": USER_AGENT}
    )
    resp.raise_for_status()
    return resp.text


# ─── Parsing ─────────────────────────────────────────────────────────────────


def parse_pub_date(s: str) -> Optional[datetime]:
    """Parse an RFC 822 RSS <pubDate> string into a UTC-aware datetime."""
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_episode_number(title: str) -> Optional[int]:
    """Pull the episode number out of a CR title."""
    m = EPISODE_RE.search(title)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def extract_show_title(title: str) -> str:
    """Return the show portion of a CR title, with the 'Episode N' tail stripped."""
    parts = EPISODE_RE.split(title, maxsplit=1)
    head = parts[0]
    head = re.sub(r"[\s\-–:]+$", "", head).strip()
    return head or title.strip()


def parse_rss(xml_text: str) -> list[CrunchyrollEntry]:
    """Parse RSS 2.0 XML into a list of normalized entries."""
    root = ET.fromstring(xml_text)
    entries: list[CrunchyrollEntry] = []
    for item in root.iter("item"):
        raw_title = (item.findtext("title") or "").strip()
        pub_str = (item.findtext("pubDate") or "").strip()
        if not raw_title or not pub_str:
            continue
        pub_dt = parse_pub_date(pub_str)
        if not pub_dt:
            continue
        entries.append(
            CrunchyrollEntry(
                raw_title=raw_title,
                show_title=extract_show_title(raw_title),
                episode_number=extract_episode_number(raw_title),
                pub_date=pub_dt,
            )
        )
    return entries


# ─── Fuzzy matching ──────────────────────────────────────────────────────────


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"\w+", s.lower()))


def token_set_ratio(a: str, b: str) -> float:
    """Token-set similarity (0–100). Robust to word order and extra subtitles.

    Backed by rapidfuzz's C-level implementation — same algorithm as the
    previous difflib.SequenceMatcher version but ~100-1000x faster, which
    matters because best_match() calls this 25,000+ times per AnimeSchedule
    entry.
    """
    from rapidfuzz import fuzz as _rf_fuzz

    if not a or not b:
        return 0.0
    return float(_rf_fuzz.token_set_ratio(a, b))


def _strip_season(s: str) -> str:
    out = SEASON_SUFFIX_RE.sub("", s).strip()
    return out or s


def best_match(show_title: str, candidates: Iterable) -> tuple[Optional[object], float]:
    """Pick the Anime with the highest token-set ratio across (title, title_english).

    Uses rapidfuzz.process.extractOne for the inner scan so the candidate loop
    runs in C (was 4+ hours of pure-Python SequenceMatcher on a 25k catalog,
    now seconds).
    """
    from rapidfuzz import fuzz as _rf_fuzz
    from rapidfuzz import process as _rf_process

    query = (show_title or "").strip()
    if not query:
        return None, 0.0
    query_season = _parse_season(query)

    # Flatten (anime, field) -> full title string (NOT season-stripped, so a
    # later-season feed can match the correct season's row). Materialize so we
    # can index by position into the rapidfuzz result.
    candidates = list(candidates)
    titles: list[str] = []
    owners: list[object] = []
    seasons: list[int] = []
    for anime in candidates:
        for cand in (anime.title, getattr(anime, "title_english", None)):
            if not cand:
                continue
            titles.append(cand)
            owners.append(anime)
            seasons.append(_parse_season(cand))

    if not titles:
        return None, 0.0

    # Score every candidate in C (fast), keep the top matches, then re-rank the
    # short list with a season penalty so e.g. "... Season 7" can't land on the
    # base/Season-1 row. The penalty is applied to the returned score, so a
    # season-only mismatch falls below the caller's accept threshold (no dub).
    top = _rf_process.extract(
        query, titles, scorer=_rf_fuzz.token_set_ratio, limit=25
    )
    best_owner = None
    best_adj = -1.0
    for _matched_title, score, idx in top:
        adj = score
        if seasons[idx] != query_season:
            adj -= SEASON_MISMATCH_PENALTY
        if adj > best_adj:
            best_adj = adj
            best_owner = owners[idx]

    if best_owner is None:
        return None, 0.0
    return best_owner, max(0.0, best_adj)


# ─── Top-level ingest ────────────────────────────────────────────────────────


def ingest_feed(
    xml_text: str,
    *,
    dry_run: bool = False,
    since: Optional[datetime] = None,
    threshold: float = MATCH_THRESHOLD,
) -> dict:
    """Parse RSS, fuzzy-match, upsert Episode rows. Returns a summary dict.

    Idempotent: an Episode is identified by (anime_id, episode_number); reruns
    re-write the same air_date_dub + dub_source rather than duplicate.
    """
    # Imported lazily so this module is importable without a DB context.
    from models import db, Anime, Episode

    summary = IngestSummary(dry_run=dry_run)
    entries = parse_rss(xml_text)
    if since is not None:
        entries = [e for e in entries if e.pub_date >= since]
    summary.parsed = len(entries)
    if not entries:
        return summary.to_dict()

    # Load only the columns best_match needs as a lightweight namedtuple
    # instead of full Anime ORM instances. Drops candidate-list memory
    # ~30x on a 25k-anime catalog (mirrors the AnimeSchedule fix).
    from collections import namedtuple as _nt
    _AnimeCand = _nt("_AnimeCand", ["id", "title", "title_english"])
    candidates = [
        _AnimeCand(row.id, row.title, row.title_english)
        for row in db.session.query(
            Anime.id, Anime.title, Anime.title_english
        ).all()
    ]
    for entry in entries:
        if entry.episode_number is None:
            summary.skipped_no_episode_number += 1
            continue
        anime, score = best_match(entry.show_title, candidates)
        if anime is None or score < threshold:
            summary.unmatched += 1
            summary.unmatched_titles.append(
                {"title": entry.show_title, "score": round(score, 1)}
            )
            continue
        summary.matched += 1
        if dry_run:
            continue
        ep = (
            Episode.query
            .filter_by(anime_id=anime.id, episode_number=entry.episode_number)
            .first()
        )
        if ep is None:
            ep = Episode(
                anime_id=anime.id, episode_number=entry.episode_number
            )
            db.session.add(ep)
        ep.air_date_dub = entry.pub_date
        ep.dub_source = DUB_SOURCE
        summary.written += 1

    if not dry_run:
        db.session.commit()
    return summary.to_dict()
