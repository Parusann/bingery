"""Compose the JSON context passed to the LLM for chat.

Pulls a (cached) signal profile, strips cache-only fields, enriches it with
the user's full picture (watchlist by status, favorites, review snippets)
for recommend + rate modes, and conditionally attaches the candidates array
for recommend mode. The enriched user block is budgeted so a heavy account
can never blow up the system prompt.
"""
import json

from models import db, Anime, Rating, WatchlistEntry
from routes.rec_signals import get_signal_profile, score_candidates


_CACHE_ONLY_FIELDS = ("schema_version", "computed_at", "rating_count_at_compute")
_RECOMMEND_LIMIT = 40
_RECOMMEND_LIMIT_COLD = 80
_GROUP_CAP = 15  # titles per watchlist status group
_REVIEW_CAP = 5
_REVIEW_SNIPPET = 280
_USER_BLOCK_BUDGET = 8192  # bytes of JSON for the enriched user block


def _watchlist_groups(user_id):
    """Titles grouped by watchlist status, plus favorited titles."""
    rows = (
        db.session.query(WatchlistEntry.status, WatchlistEntry.is_favorite, Anime.title)
        .join(Anime, Anime.id == WatchlistEntry.anime_id)
        .filter(WatchlistEntry.user_id == user_id)
        .all()
    )
    groups: dict[str, list[str]] = {}
    favorites: list[str] = []
    for status, is_favorite, title in rows:
        groups.setdefault(status, []).append(title)
        if is_favorite:
            favorites.append(title)
    return (
        {status: titles[:_GROUP_CAP] for status, titles in groups.items()},
        favorites[:_GROUP_CAP],
    )


def _review_snippets(user_id):
    """The user's most opinionated reviews — the WHY behind the scores.
    Strong opinions (|score - 5.5| large) carry the most signal."""
    rows = (
        db.session.query(Rating.score, Rating.review, Anime.title)
        .join(Anime, Anime.id == Rating.anime_id)
        .filter(
            Rating.user_id == user_id,
            Rating.review.isnot(None),
            Rating.review != "",
        )
        .all()
    )
    rows.sort(key=lambda r: -abs(r[0] - 5.5))
    return [
        {"title": title, "score": score, "snippet": (review or "")[:_REVIEW_SNIPPET]}
        for score, review, title in rows[:_REVIEW_CAP]
    ]


def _shrink_user_block(user_block, budget=_USER_BLOCK_BUDGET):
    """Trim the enriched block to the byte budget: watchlist group tails go
    first, then favorites, then reviews — reviews are the richest signal."""

    def _size():
        return len(json.dumps(user_block))

    while _size() > budget:
        watchlist = user_block.get("watchlist") or {}
        longest = max(watchlist, key=lambda k: len(watchlist[k]), default=None)
        if longest and watchlist[longest]:
            watchlist[longest].pop()
            continue
        if user_block.get("favorites"):
            user_block["favorites"].pop()
            continue
        if user_block.get("reviews"):
            user_block["reviews"].pop()
            continue
        break  # nothing left to trim; profile core stays
    return user_block


def build_llm_context(user_id, message, mode, include_nsfw=False):
    """Return the JSON dict to embed in the LLM system prompt.

    mode: 'recommend' | 'rate' | 'onboard'
    """
    profile = get_signal_profile(user_id)
    user_block = {k: v for k, v in profile.items() if k not in _CACHE_ONLY_FIELDS}

    if mode in ("recommend", "rate"):
        groups, favorites = _watchlist_groups(user_id)
        user_block["watchlist"] = groups
        user_block["favorites"] = favorites
        user_block["reviews"] = _review_snippets(user_id)
        user_block = _shrink_user_block(user_block)

    out = {
        "mode": mode,
        "user_message": message,
        "user": user_block,
    }

    if mode == "recommend":
        limit = _RECOMMEND_LIMIT_COLD if profile["rating_count_at_compute"] == 0 else _RECOMMEND_LIMIT
        out["candidates"] = score_candidates(user_id, profile, limit=limit, include_nsfw=include_nsfw)

    return out
