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
    """Token-set similarity (0–100). Robust to word order and extra subtitles."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    intersection = sorted(ta & tb)
    diff_a = sorted(ta - tb)
    diff_b = sorted(tb - ta)
    s1 = " ".join(intersection)
    s2 = " ".join(intersection + diff_a)
    s3 = " ".join(intersection + diff_b)
    if not s1:
        joined_a = " ".join(sorted(ta))
        joined_b = " ".join(sorted(tb))
        return SequenceMatcher(None, joined_a, joined_b).ratio() * 100.0
    r1 = SequenceMatcher(None, s1, s2).ratio()
    r2 = SequenceMatcher(None, s1, s3).ratio()
    r3 = SequenceMatcher(None, s2, s3).ratio()
    return max(r1, r2, r3) * 100.0


def _strip_season(s: str) -> str:
    out = SEASON_SUFFIX_RE.sub("", s).strip()
    return out or s


def best_match(show_title: str, candidates: Iterable) -> tuple[Optional[object], float]:
    """Pick the Anime with the highest token-set ratio across (title, title_english)."""
    best = None
    best_score = 0.0
    norm_query = _strip_season(show_title)
    for anime in candidates:
        for cand in (anime.title, getattr(anime, "title_english", None)):
            if not cand:
                continue
            norm_cand = _strip_season(cand)
            score = token_set_ratio(norm_query, norm_cand)
            if score > best_score:
                best_score = score
                best = anime
    return best, best_score


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

    candidates = Anime.query.all()
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
