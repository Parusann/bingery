"""Seed-based anime similarity: pure scoring functions + catalog ranking.

Everything above `get_tag_index` is unit-testable without an app context —
no Flask or model imports in the math section. The design doc is
docs/superpowers/specs/2026-07-01-chat-similarity-revamp-design.md.
"""
from __future__ import annotations

import math
import re
import time

ERA_SIGMA_YEARS = 8.0

WEIGHTS = {
    "tags": 45,
    "genres": 20,
    "fan_genres": 10,
    "format": 10,
    "quality": 10,
    "era": 5,
}


def weighted_jaccard(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    mx = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    if mx == 0:
        return 0.0
    return sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys) / mx


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def source_bucket(source: str | None) -> str:
    s = (source or "").lower()
    if "manga" in s:
        return "manga"
    if "novel" in s:
        return "novel"
    if s == "original":
        return "original"
    return "other"


def episode_bucket(episodes: int | None) -> str:
    if episodes is None:
        return "medium"
    if episodes <= 13:
        return "short"
    if episodes <= 26:
        return "medium"
    return "long"


def era_proximity(year_a: int | None, year_b: int | None) -> float:
    if year_a is None or year_b is None:
        return 0.5
    return math.exp(-((year_a - year_b) ** 2) / (2 * ERA_SIGMA_YEARS**2))


def build_feature_from_parts(
    *, tags, genres, fan_genres, source, episodes, year, quality
) -> dict:
    """Normalize raw fields into the vector `similarity_score` consumes.

    tags: {name: rank/100}; quality: max(api, community)/10, clamped [0, 1].
    """
    return {
        "tags": dict(tags or {}),
        "genres": set(genres or ()),
        "fan_genres": set(fan_genres or ()),
        "source_bucket": source_bucket(source),
        "episode_bucket": episode_bucket(episodes),
        "year": year,
        "quality": max(0.0, min(1.0, quality or 0.0)),
    }


def similarity_score(seed: dict, cand: dict) -> float:
    """0-100. A tagless seed (not yet backfilled) redistributes the tag
    weight proportionally across the other components instead of zeroing
    45 points for every candidate."""
    comps = {
        "tags": weighted_jaccard(seed["tags"], cand["tags"]),
        "genres": jaccard(seed["genres"], cand["genres"]),
        "fan_genres": jaccard(seed["fan_genres"], cand["fan_genres"]),
        "format": (
            (seed["source_bucket"] == cand["source_bucket"])
            + (seed["episode_bucket"] == cand["episode_bucket"])
        ) / 2,
        "quality": cand["quality"],
        "era": era_proximity(seed["year"], cand["year"]),
    }
    weights = dict(WEIGHTS)
    if not seed["tags"]:
        spread = weights.pop("tags")
        total = sum(weights.values())
        weights = {k: w + spread * (w / total) for k, w in weights.items()}
        weights["tags"] = 0
    return sum(weights[k] * comps[k] for k in comps)


# ─── Catalog-backed helpers (need an app context) ───────────────────────────

_TAG_INDEX: dict[int, dict[str, int]] | None = None
_TAG_INDEX_AT: float = 0.0
TAG_INDEX_TTL = 6 * 3600  # catalog syncs are weekly; 6h is generous

_ROOT_NOISE = re.compile(
    r"\b(season|part|cour|movie|film|ova|ona|special|final)\b.*$"
    r"|\b(2nd|3rd|\dth|s\d+|ii|iii|iv)\b.*$"
    r"|[:\-–]\s.*$"
    r"|\s+\d+\s*$",
    re.IGNORECASE,
)


def title_root(title: str) -> str:
    """Franchise fallback key: 'Re:Zero Season 2' -> 're:zero'. Never empty —
    a stripped-to-nothing root would franchise-match unrelated titles."""
    lowered = (title or "").lower()
    root = _ROOT_NOISE.sub("", lowered).strip()
    return root or lowered.strip()


def get_tag_index(force_refresh: bool = False) -> dict[int, dict[str, int]]:
    """{anime_id: {tag_name: rank}} for the whole catalog, cached in-process."""
    global _TAG_INDEX, _TAG_INDEX_AT
    if (
        not force_refresh
        and _TAG_INDEX is not None
        and time.time() - _TAG_INDEX_AT < TAG_INDEX_TTL
    ):
        return _TAG_INDEX
    from models import db, AnimeTag, Tag

    rows = (
        db.session.query(AnimeTag.anime_id, Tag.name, AnimeTag.rank)
        .join(Tag, Tag.id == AnimeTag.tag_id)
        .all()
    )
    idx: dict[int, dict[str, int]] = {}
    for anime_id, name, rank in rows:
        idx.setdefault(anime_id, {})[name] = rank
    _TAG_INDEX, _TAG_INDEX_AT = idx, time.time()
    return idx


def franchise_anilist_ids(seed) -> set[int]:
    """AniList ids in the seed's franchise via the cached relations BFS.
    Empty set on any failure — callers also apply the title_root guard,
    which never needs the network."""
    if not getattr(seed, "anilist_id", None):
        return set()
    try:
        from utils.anilist import AniListClient, assemble_franchise

        client = AniListClient()
        nodes = assemble_franchise(seed.anilist_id, client.get_anime_relations)
        return set(nodes.keys())
    except Exception:
        return set()
