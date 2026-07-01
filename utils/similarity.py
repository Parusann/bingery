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


def _cache_only_relations(anilist_id):
    """Read a relations entry from the AniList client's in-process cache
    (warmed by /related). Raises on miss so assemble_franchise skips the
    node instead of fetching."""
    from utils import anilist as al

    hit = al._RELATIONS_CACHE.get(anilist_id)
    if hit is None:
        raise LookupError("relations not cached")
    return hit[1]


def franchise_anilist_ids(seed, allow_network: bool = True) -> set[int]:
    """AniList ids in the seed's franchise via the relations BFS.

    allow_network=False walks only the already-cached relations graph —
    page surfaces (/similar, For You) must never block on AniList; the
    /related call on the same detail page warms this cache. The chat tool
    uses allow_network=True where a few seconds of accuracy is worth it.
    Empty set on any failure — callers also apply the title_root guard.
    """
    if not getattr(seed, "anilist_id", None):
        return set()
    try:
        from utils.anilist import AniListClient, assemble_franchise

        if allow_network:
            fetch = AniListClient().get_anime_relations
        else:
            fetch = _cache_only_relations
        nodes = assemble_franchise(seed.anilist_id, fetch)
        return set(nodes.keys())
    except Exception:
        return set()


def _fan_genre_index() -> dict[int, set[str]]:
    """{anime_id: voted fan-genre tags} in one grouped query (avoids the
    2-queries-per-anime cost of Anime.get_fan_genres over the catalog)."""
    from models import db, FanGenreVote

    idx: dict[int, set[str]] = {}
    for anime_id, tag in db.session.query(
        FanGenreVote.anime_id, FanGenreVote.genre_tag
    ):
        idx.setdefault(anime_id, set()).add(tag)
    return idx


def _community_score_index() -> dict[int, float]:
    """{anime_id: avg rating} in one grouped query — calling
    get_community_score() per candidate is an N+1 over the whole catalog."""
    from sqlalchemy import func

    from models import Rating, db

    return {
        anime_id: float(avg)
        for anime_id, avg in db.session.query(
            Rating.anime_id, func.avg(Rating.score)
        ).group_by(Rating.anime_id)
    }


def _feature_for(anime, tag_index, fan_index, score_index) -> dict:
    quality_10 = max(anime.api_score or 0.0, score_index.get(anime.id, 0.0))
    return build_feature_from_parts(
        tags={n: r / 100 for n, r in tag_index.get(anime.id, {}).items()},
        genres={g.name for g in anime.official_genres},
        fan_genres=fan_index.get(anime.id, set()),
        source=anime.source,
        episodes=anime.episodes,
        year=anime.year,
        quality=quality_10 / 10,
    )


def similar_to(
    seed, limit=12, user_id=None, include_nsfw=False, franchise_network=False
) -> dict:
    """Rank the catalog against `seed`.

    Returns {"similar": [card + match_score/shared_tags/in_plan_to_watch],
             "franchise": [unwatched same-franchise cards]}.
    Personalized (user_id set): final = 0.7*similarity + 0.3*personal
    (rec_signals score), minus anything the user rated or has on the
    watchlist in any status except plan_to_watch.
    franchise_network: pass True only where blocking on AniList is
    acceptable (the chat tool); page surfaces stay cache-only.
    """
    from sqlalchemy.orm import selectinload

    from models import Anime, Rating, WatchlistEntry, db
    from utils.nsfw import exclude_hard_blocked, exclude_soft_blocked

    tag_index = get_tag_index()
    fan_index = _fan_genre_index()
    score_index = _community_score_index()
    seed_feat = _feature_for(seed, tag_index, fan_index, score_index)
    fam_anilist = franchise_anilist_ids(seed, allow_network=franchise_network)
    seed_root = title_root(seed.title)

    query = db.session.query(Anime)
    query = exclude_hard_blocked(query)
    if not include_nsfw:
        query = exclude_soft_blocked(query)
    candidates = query.options(selectinload(Anime.official_genres)).all()

    excluded_user_ids: set[int] = set()
    plan_ids: set[int] = set()
    profile = None
    top_100_ids: set[int] = set()
    if user_id is not None:
        from routes.rec_signals import get_signal_profile, score_candidate

        profile = get_signal_profile(user_id)
        excluded_user_ids = {
            r[0]
            for r in db.session.query(Rating.anime_id).filter(
                Rating.user_id == user_id
            )
        }
        for anime_id, status in db.session.query(
            WatchlistEntry.anime_id, WatchlistEntry.status
        ).filter(WatchlistEntry.user_id == user_id):
            if status == "plan_to_watch":
                plan_ids.add(anime_id)
            else:
                excluded_user_ids.add(anime_id)
        top_100_ids = {
            a[0]
            for a in db.session.query(Anime.id)
            .filter(Anime.popularity.isnot(None))
            .order_by(Anime.popularity.desc())
            .limit(100)
        }

    scored, franchise = [], []
    for c in candidates:
        if c.id == seed.id:
            continue
        if c.anilist_id in fam_anilist or title_root(c.title) == seed_root:
            if c.id not in excluded_user_ids:
                franchise.append(c)
            continue
        if c.id in excluded_user_ids:
            continue
        s = similarity_score(
            seed_feat, _feature_for(c, tag_index, fan_index, score_index)
        )
        if profile is not None:
            personal = score_candidate(
                {
                    "id": c.id,
                    "title": c.title,
                    "studio": c.studio,
                    "genres": [g.name for g in c.official_genres],
                    "fan_genres": sorted(fan_index.get(c.id, set())),
                    "api_score": c.api_score,
                    "year": c.year,
                    "episodes": c.episodes,
                },
                profile,
                top_100_ids,
            )["signals"]["total_score"]
            s = 0.7 * s + 0.3 * personal
        shared = sorted(
            set(tag_index.get(seed.id, {})) & set(tag_index.get(c.id, {})),
            key=lambda n: -tag_index[c.id][n],
        )[:4]
        scored.append((s, c, shared))

    def _card(c):
        # include_community fires 3 queries per card (score, count, fan
        # genres) — fill the score from the batch index instead.
        d = c.to_dict(include_community=False)
        d["community_score"] = (
            round(score_index[c.id], 2) if c.id in score_index else None
        )
        return d

    scored.sort(key=lambda t: (-t[0], t[1].id))
    return {
        "similar": [
            {
                **_card(c),
                "match_score": round(s, 1),
                "shared_tags": shared,
                "in_plan_to_watch": c.id in plan_ids,
            }
            for s, c, shared in scored[:limit]
        ],
        "franchise": [_card(c) for c in franchise[:6]],
    }
