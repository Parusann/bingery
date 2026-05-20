"""Shared NSFW-filtering helpers used across anime list endpoints.

Two tiers:

* HARD_BLOCKED_GENRES — always filtered out, no opt-in. Hentai stays hidden
  even if the caller sends ``?include_nsfw=true``.
* SOFT_BLOCKED_GENRES — hidden by default; the global Header toggle and the
  ``?include_nsfw=true`` query string flip these on.

Centralized so every list-style endpoint (/api/anime, /api/seasonal,
/api/recommend, /api/schedule, ...) applies the same rule.
"""

from flask import request

from models import db, Anime, Genre, anime_genres


# Always excluded from list endpoints regardless of toggle state.
HARD_BLOCKED_GENRES: tuple[str, ...] = ("Hentai",)

# Hidden by default; revealed when the caller opts in via ``?include_nsfw=true``.
SOFT_BLOCKED_GENRES: tuple[str, ...] = ("Ecchi",)


def include_nsfw_requested() -> bool:
    """True iff the current request opted in via ``?include_nsfw=true``."""
    return request.args.get("include_nsfw", "false").lower() == "true"


def _anime_ids_tagged_with(names: tuple[str, ...]):
    """Subquery yielding anime_ids tagged with any of ``names``."""
    return (
        db.session.query(anime_genres.c.anime_id)
        .join(Genre, Genre.id == anime_genres.c.genre_id)
        .filter(Genre.name.in_(names))
    )


def exclude_hard_blocked(query):
    """Always-on filter: drop anime tagged with HARD_BLOCKED_GENRES."""
    return query.filter(~Anime.id.in_(_anime_ids_tagged_with(HARD_BLOCKED_GENRES)))


def exclude_soft_blocked(query):
    """Drop anime tagged with SOFT_BLOCKED_GENRES (Ecchi)."""
    return query.filter(~Anime.id.in_(_anime_ids_tagged_with(SOFT_BLOCKED_GENRES)))


def maybe_exclude_nsfw(query):
    """Apply the standard tiered NSFW policy to ``query``.

    Works for any query that has ``Anime`` in its FROM clause — flat
    ``Anime.query``, ``db.session.query(Anime)``, or a join like
    ``db.session.query(Episode, Anime).join(Anime, ...)``.
    """
    query = exclude_hard_blocked(query)
    if not include_nsfw_requested():
        query = exclude_soft_blocked(query)
    return query
