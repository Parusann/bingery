"""
AniList GraphQL API integration for Bingery.

AniList's API is free, requires no auth key, and has comprehensive anime data.
Docs: https://anilist.gitbook.io/anilist-apiv2-docs

Usage:
    from utils.anilist import AniListClient
    client = AniListClient()

    # Search for anime
    results = client.search_anime("Frieren")

    # Get full details
    details = client.get_anime(154587)

    # Sync to database
    from utils.anilist import sync_anime_from_anilist
    sync_anime_from_anilist(app, query="popular", page=1, per_page=50)
"""

import requests
import time
from typing import Optional

ANILIST_API = "https://graphql.anilist.co"

# Rate limit: 90 requests per minute. We add small delays to stay safe.
RATE_LIMIT_DELAY = 0.7  # seconds between requests

# Per-title relations cache (anilist_id -> (fetched_at, normalized_dict)).
# AniList relations change rarely; the app runs a single gunicorn worker so
# this in-process cache is effectively global.
_RELATIONS_CACHE: dict = {}
RELATIONS_CACHE_TTL = 60 * 60 * 24  # 24 hours


# ═══════════════════════════════════════════════════════════════════════════════
# GraphQL Queries
# ═══════════════════════════════════════════════════════════════════════════════

SEARCH_QUERY = """
query ($search: String, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total currentPage lastPage hasNextPage }
    media(search: $search, type: ANIME, sort: POPULARITY_DESC) {
      ...AnimeFields
    }
  }
}
"""

POPULAR_QUERY = """
query ($page: Int, $perPage: Int, $season: MediaSeason, $seasonYear: Int, $sort: [MediaSort]) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total currentPage lastPage hasNextPage }
    media(type: ANIME, sort: $sort, season: $season, seasonYear: $seasonYear) {
      ...AnimeFields
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    ...AnimeFields
  }
}
"""

# Self-contained relations query — deliberately does NOT use ...AnimeFields,
# so it is sent via _execute() (no fragment append) and keeps the shared
# catalog-sync payload unchanged. Relation nodes carry the fields the
# franchise strip needs: format, dates, cover art, and media type.
RELATIONS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    type
    title { romaji english }
    format
    seasonYear
    startDate { year month day }
    coverImage { large medium }
    relations {
      edges {
        relationType
        node {
          id
          type
          title { romaji english }
          format
          seasonYear
          startDate { year month day }
          coverImage { large medium }
        }
      }
    }
  }
}
"""

# AniList MediaFormat -> display label for the franchise strip.
FORMAT_LABELS = {
    "TV": "TV",
    "TV_SHORT": "TV Short",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}

ANIME_FRAGMENT = """
fragment AnimeFields on Media {
  id
  idMal
  title {
    romaji
    english
    native
  }
  description(asHtml: false)
  averageScore
  meanScore
  popularity
  favourites
  seasonYear
  season
  episodes
  duration
  status
  source
  genres
  tags {
    name
    rank
    category
  }
  studios(isMain: true) {
    nodes { name }
  }
  coverImage {
    extraLarge
    large
    medium
  }
  bannerImage
  startDate { year month day }
  endDate { year month day }
  nextAiringEpisode {
    airingAt
    episode
  }
  relations {
    edges {
      relationType
      node {
        id
        title { romaji english }
        type
      }
    }
  }
}
"""


# Full-catalog paginated query used by sync_anilist.py — chunked by seasonYear.
#
# IMPORTANT: AniList caps deep page-based pagination at offset 5000 (page 100
# with perPage=50) AND does not expose `id_greater` on Media. The workaround
# is to chunk by `seasonYear`; each year has well under 5000 anime, so
# standard page-based pagination works cleanly within each year. We iterate
# years one at a time. Anime with `seasonYear: null` (rare; mostly unscheduled
# specials and OVAs) are not reachable via this query and remain unsynced —
# known coverage gap.
CATALOG_QUERY = """
query ($page: Int, $perPage: Int, $seasonYear: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage currentPage lastPage perPage }
    media(type: ANIME, sort: ID, seasonYear: $seasonYear) {
      ...AnimeFields
      nextAiringEpisode {
        airingAt
        episode
        timeUntilAiring
      }
      airingSchedule {
        nodes {
          episode
          airingAt
        }
      }
    }
  }
}
"""


# Orphan-catcher query — paginates by `format` instead of `seasonYear` so we
# can reach entries with `seasonYear: null` (typically older SPECIAL / OVA /
# ONA / MUSIC entries that the year-chunker misses). Per-format catalogs are
# small enough that page-based pagination fits under AniList's 5000-offset
# cap — verified for SPECIAL, OVA, ONA, MUSIC, TV_SHORT.
CATALOG_QUERY_BY_FORMAT = """
query ($page: Int, $perPage: Int, $format: MediaFormat) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage currentPage lastPage perPage }
    media(type: ANIME, sort: ID, format: $format) {
      ...AnimeFields
      nextAiringEpisode {
        airingAt
        episode
        timeUntilAiring
      }
      airingSchedule {
        nodes {
          episode
          airingAt
        }
      }
    }
  }
}
"""


class AniListClient:
    """Client for the AniList GraphQL API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._last_request_time = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        # Existing callers rely on the shared AnimeFields fragment being appended.
        return self._execute(query + ANIME_FRAGMENT, variables)

    def _execute(self, full_query: str, variables: Optional[dict] = None) -> dict:
        """Send an already-complete GraphQL document (no fragment appended)."""
        self._rate_limit()
        payload = {"query": full_query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(ANILIST_API, json=payload, timeout=15)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            return self._execute(full_query, variables)

        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise Exception(f"AniList API error: {data['errors']}")

        return data["data"]

    @staticmethod
    def _normalize_relation_node(node: dict) -> dict:
        start = node.get("startDate") or {}
        year, month, day = start.get("year"), start.get("month"), start.get("day")
        release_date = None
        if year and month and day:
            release_date = f"{year:04d}-{month:02d}-{day:02d}"
        title = node.get("title") or {}
        cover = node.get("coverImage") or {}
        return {
            "anilist_id": node.get("id"),
            "title": title.get("english") or title.get("romaji") or "Unknown",
            "format": FORMAT_LABELS.get(node.get("format")),
            "year": year or node.get("seasonYear"),
            "month": month,
            "day": day,
            "release_date": release_date,
            "image_url": cover.get("large") or cover.get("medium"),
            "type": node.get("type"),
        }

    def _normalize_relations(self, media: dict) -> dict:
        """Shape a RELATIONS_QUERY Media object into {self, edges}."""
        edges = []
        for edge in (media.get("relations") or {}).get("edges", []):
            edges.append({
                "relation_type": edge.get("relationType"),
                "node": self._normalize_relation_node(edge.get("node") or {}),
            })
        return {"self": self._normalize_relation_node(media), "edges": edges}

    def get_anime_relations(self, anilist_id: int) -> dict:
        """Fetch + normalize one title's relations, cached for RELATIONS_CACHE_TTL."""
        now = time.time()
        cached = _RELATIONS_CACHE.get(anilist_id)
        if cached and now - cached[0] < RELATIONS_CACHE_TTL:
            return cached[1]
        data = self._execute(RELATIONS_QUERY, {"id": anilist_id})
        result = self._normalize_relations(data["Media"])
        _RELATIONS_CACHE[anilist_id] = (now, result)
        return result

    def _normalize_anime(self, media: dict) -> dict:
        """Convert AniList media object to Bingery's internal format."""
        studios = media.get("studios", {}).get("nodes", [])
        studio_name = studios[0]["name"] if studios else None

        # Map AniList status to Bingery status
        status_map = {
            "FINISHED": "Finished Airing",
            "RELEASING": "Currently Airing",
            "NOT_YET_RELEASED": "Upcoming",
            "CANCELLED": "Cancelled",
            "HIATUS": "On Hiatus",
        }

        # Map AniList source to readable format
        source_map = {
            "ORIGINAL": "Original",
            "MANGA": "Manga",
            "LIGHT_NOVEL": "Light Novel",
            "VISUAL_NOVEL": "Visual Novel",
            "VIDEO_GAME": "Video Game",
            "NOVEL": "Novel",
            "WEB_NOVEL": "Web Novel",
            "ONE_SHOT": "One Shot",
            "DOUJINSHI": "Doujinshi",
            "ANIME": "Anime",
            "WEB_MANGA": "Web Manga",
            "LIVE_ACTION": "Live Action",
            "GAME": "Game",
            "COMIC": "Comic",
            "MULTIMEDIA_PROJECT": "Multimedia Project",
            "PICTURE_BOOK": "Picture Book",
            "OTHER": "Other",
        }

        season_map = {
            "WINTER": "winter",
            "SPRING": "spring",
            "SUMMER": "summer",
            "FALL": "fall",
        }

        cover = media.get("coverImage", {})

        # Clean description (remove HTML-like brackets that slip through)
        description = media.get("description") or ""
        description = description.replace("<br>", "\n").replace("<br/>", "\n")
        description = description.replace("<i>", "").replace("</i>", "")
        description = description.replace("<b>", "").replace("</b>", "")

        # Extract high-ranked tags (rank > 60%) as supplementary genre info
        tags = []
        for tag in media.get("tags", []):
            if tag.get("rank", 0) >= 60:
                tags.append({
                    "name": tag["name"],
                    "rank": tag["rank"],
                    "category": tag.get("category", ""),
                })

        return {
            "anilist_id": media["id"],
            "mal_id": media.get("idMal"),
            "title": media["title"].get("romaji") or media["title"].get("english") or "Unknown",
            "title_english": media["title"].get("english"),
            "title_japanese": media["title"].get("native"),
            "synopsis": description,
            "api_score": (media.get("averageScore") or 0) / 10,  # AniList is 0-100, we use 0-10
            "year": media.get("seasonYear") or (media.get("startDate") or {}).get("year"),
            "season": season_map.get(media.get("season")),
            "episodes": media.get("episodes"),
            "studio": studio_name,
            "image_url": cover.get("extraLarge") or cover.get("large") or cover.get("medium"),
            "banner_url": media.get("bannerImage"),
            "status": status_map.get(media.get("status"), "Unknown"),
            "source": source_map.get(media.get("source"), media.get("source")),
            "genres": media.get("genres", []),
            "tags": tags,  # Extra: detailed tags with rankings
            "popularity": media.get("popularity"),
            "favourites": media.get("favourites"),
        }

    # ── Public methods ────────────────────────────────────────────────────

    def search_anime(self, query: str, page: int = 1, per_page: int = 20) -> dict:
        """Search anime by title."""
        data = self._request(SEARCH_QUERY, {
            "search": query,
            "page": page,
            "perPage": per_page,
        })
        page_data = data["Page"]
        return {
            "results": [self._normalize_anime(m) for m in page_data["media"]],
            "page_info": page_data["pageInfo"],
        }

    def get_anime(self, anilist_id: int) -> dict:
        """Get full details for a single anime by AniList ID."""
        data = self._request(DETAIL_QUERY, {"id": anilist_id})
        return self._normalize_anime(data["Media"])

    def get_popular(
        self,
        page: int = 1,
        per_page: int = 50,
        sort: str = "POPULARITY_DESC",
        season: Optional[str] = None,
        season_year: Optional[int] = None,
    ) -> dict:
        """
        Get popular/trending anime.
        sort options: POPULARITY_DESC, SCORE_DESC, TRENDING_DESC, FAVOURITES_DESC, START_DATE_DESC
        season: WINTER, SPRING, SUMMER, FALL
        """
        variables = {"page": page, "perPage": per_page, "sort": [sort]}
        if season:
            variables["season"] = season
        if season_year:
            variables["seasonYear"] = season_year

        data = self._request(POPULAR_QUERY, variables)
        page_data = data["Page"]
        return {
            "results": [self._normalize_anime(m) for m in page_data["media"]],
            "page_info": page_data["pageInfo"],
        }

    def get_top_rated(self, page: int = 1, per_page: int = 50) -> dict:
        """Get top-rated anime of all time."""
        return self.get_popular(page, per_page, sort="SCORE_DESC")

    def get_trending(self, page: int = 1, per_page: int = 50) -> dict:
        """Get currently trending anime."""
        return self.get_popular(page, per_page, sort="TRENDING_DESC")

    def get_seasonal(
        self, year: int, season: str, page: int = 1, per_page: int = 50
    ) -> dict:
        """Get anime for a specific season (e.g., Winter 2024)."""
        return self.get_popular(
            page, per_page, sort="POPULARITY_DESC",
            season=season.upper(), season_year=year,
        )

    def fetch_catalog_page(
        self, season_year: int, page: int = 1, per_page: int = 50
    ) -> dict:
        """
        Fetch one page of AniList anime for a given seasonYear.

        AniList caps deep pagination at offset 5000 AND does not expose
        `id_greater`, so the only way to walk the entire catalog is to chunk by
        `seasonYear`. Each year has well under 5000 anime, so standard
        page-based pagination works cleanly within each year.

        Returns a dict with:
          - "media":      list of normalized anime dicts (same shape as
                          _normalize_anime), plus "next_airing_episode" and
                          "airing_schedule" keys for episode tracking.
          - "page_info":  raw AniList pageInfo with hasNextPage, currentPage,
                          lastPage, perPage.

        Used by sync_anilist.py to drive the resumable full-catalog sync.
        """
        data = self._request(
            CATALOG_QUERY,
            {"page": page, "perPage": per_page, "seasonYear": season_year},
        )
        page_data = data["Page"]

        media_list = []
        for raw in page_data["media"]:
            normalized = self._normalize_anime(raw)
            normalized["next_airing_episode"] = raw.get("nextAiringEpisode") or None
            normalized["airing_schedule"] = (
                (raw.get("airingSchedule") or {}).get("nodes") or []
            )
            media_list.append(normalized)

        return {
            "media": media_list,
            "page_info": page_data["pageInfo"],
        }

    def fetch_catalog_page_by_format(
        self, media_format: str, page: int = 1, per_page: int = 50
    ) -> dict:
        """Fetch one page of AniList anime filtered by `format` (MediaFormat enum).

        Used by sync_anilist.py's orphan-catcher mode to reach entries with
        `seasonYear: null` — typically older SPECIAL / OVA / ONA / MUSIC entries.

        Returns the same shape as `fetch_catalog_page`.
        """
        data = self._request(
            CATALOG_QUERY_BY_FORMAT,
            {"page": page, "perPage": per_page, "format": media_format},
        )
        page_data = data["Page"]

        media_list = []
        for raw in page_data["media"]:
            normalized = self._normalize_anime(raw)
            normalized["next_airing_episode"] = raw.get("nextAiringEpisode") or None
            normalized["airing_schedule"] = (
                (raw.get("airingSchedule") or {}).get("nodes") or []
            )
            media_list.append(normalized)

        return {
            "media": media_list,
            "page_info": page_data["pageInfo"],
        }


# Relation types that belong to the same franchise "chain". Excludes
# ADAPTATION (source manga/novel), SPIN_OFF, SUMMARY (recaps), CHARACTER,
# COMPILATION, CONTAINS, OTHER, SOURCE. Single source of truth — easy to tune.
FRANCHISE_RELATION_TYPES = {"PREQUEL", "SEQUEL", "PARENT", "SIDE_STORY", "ALTERNATIVE"}
FRANCHISE_MAX_NODES = 25
FRANCHISE_MAX_DEPTH = 5


def assemble_franchise(start_id, fetch_relations,
                       max_nodes=FRANCHISE_MAX_NODES, max_depth=FRANCHISE_MAX_DEPTH):
    """Breadth-first traversal across franchise relations.

    AniList only returns direct (one-hop) relations, so we walk the graph to
    gather the whole connected franchise. `fetch_relations(anilist_id)` must
    return {"self": node, "edges": [{"relation_type", "node"}, ...]} (see
    AniListClient.get_anime_relations). Returns {anilist_id: node_dict}.
    Bounded by max_nodes (AniList calls) and max_depth (chain length).
    """
    from collections import deque

    nodes = {}
    queue = deque([(start_id, 0)])
    enqueued = {start_id}
    queries = 0

    while queue and queries < max_nodes:
        current_id, depth = queue.popleft()
        try:
            data = fetch_relations(current_id)
        except Exception:
            continue
        queries += 1
        nodes[current_id] = data["self"]          # authoritative self data
        if depth >= max_depth:
            continue
        for edge in data["edges"]:
            node = edge["node"]
            if node.get("type") != "ANIME":
                continue
            if edge["relation_type"] not in FRANCHISE_RELATION_TYPES:
                continue
            nid = node["anilist_id"]
            nodes.setdefault(nid, node)           # stub display data if unseen
            if nid not in enqueued:
                enqueued.add(nid)
                queue.append((nid, depth + 1))

    return nodes


# ═══════════════════════════════════════════════════════════════════════════════
# Database Sync
# ═══════════════════════════════════════════════════════════════════════════════


def sync_anime_to_db(anime_data: dict) -> "Anime":
    """
    Insert or update a single anime record from AniList data.
    Returns the Anime model instance.
    """
    from models import db, Anime, Genre

    # Check if we already have this anime
    anime = None
    if anime_data.get("anilist_id"):
        anime = Anime.query.filter_by(anilist_id=anime_data["anilist_id"]).first()
    if not anime and anime_data.get("mal_id"):
        anime = Anime.query.filter_by(mal_id=anime_data["mal_id"]).first()

    if anime:
        # Update existing record
        for key in [
            "title", "title_english", "title_japanese", "synopsis",
            "api_score", "popularity", "year", "season", "episodes", "studio",
            "image_url", "banner_url", "status", "source",
        ]:
            if anime_data.get(key) is not None:
                setattr(anime, key, anime_data[key])
        if anime_data.get("mal_id"):
            anime.mal_id = anime_data["mal_id"]
        if anime_data.get("anilist_id"):
            anime.anilist_id = anime_data["anilist_id"]
    else:
        # Create new record
        anime = Anime(
            anilist_id=anime_data.get("anilist_id"),
            mal_id=anime_data.get("mal_id"),
            title=anime_data["title"],
            title_english=anime_data.get("title_english"),
            title_japanese=anime_data.get("title_japanese"),
            synopsis=anime_data.get("synopsis", ""),
            api_score=anime_data.get("api_score"),
            popularity=anime_data.get("popularity"),
            year=anime_data.get("year"),
            season=anime_data.get("season"),
            episodes=anime_data.get("episodes"),
            studio=anime_data.get("studio"),
            image_url=anime_data.get("image_url"),
            banner_url=anime_data.get("banner_url"),
            status=anime_data.get("status", "Unknown"),
            source=anime_data.get("source"),
        )
        db.session.add(anime)

    # Sync official genres
    anime.official_genres.clear()
    for genre_name in anime_data.get("genres", []):
        genre = Genre.query.filter_by(name=genre_name).first()
        if not genre:
            genre = Genre(name=genre_name, category="standard")
            db.session.add(genre)
            db.session.flush()
        anime.official_genres.append(genre)

    return anime


def sync_anime_from_anilist(
    app,
    mode: str = "popular",
    query: str = "",
    pages: int = 1,
    per_page: int = 50,
    season: Optional[str] = None,
    season_year: Optional[int] = None,
):
    """
    Fetch anime from AniList and sync to the database.

    Modes:
        "popular"   — most popular of all time
        "top"       — highest rated of all time
        "trending"  — currently trending
        "seasonal"  — specific season (requires season + season_year)
        "search"    — search by query string

    Example:
        sync_anime_from_anilist(app, mode="popular", pages=3)
        sync_anime_from_anilist(app, mode="seasonal", season="WINTER", season_year=2024)
        sync_anime_from_anilist(app, mode="search", query="isekai")
    """
    from models import db

    client = AniListClient()
    total_synced = 0

    with app.app_context():
        for page in range(1, pages + 1):
            print(f"  Fetching page {page}/{pages} (mode={mode})...")

            if mode == "search":
                result = client.search_anime(query, page=page, per_page=per_page)
            elif mode == "top":
                result = client.get_top_rated(page=page, per_page=per_page)
            elif mode == "trending":
                result = client.get_trending(page=page, per_page=per_page)
            elif mode == "seasonal":
                result = client.get_seasonal(
                    season_year, season, page=page, per_page=per_page
                )
            else:  # popular
                result = client.get_popular(page=page, per_page=per_page)

            for anime_data in result["results"]:
                try:
                    anime = sync_anime_to_db(anime_data)
                    total_synced += 1
                except Exception as e:
                    print(f"    Error syncing {anime_data.get('title', '?')}: {e}")
                    continue

            db.session.commit()
            page_info = result["page_info"]
            print(f"    Synced {len(result['results'])} anime (page {page_info['currentPage']}/{page_info['lastPage']})")

            if not page_info["hasNextPage"]:
                break

        print(f"\n  Total synced: {total_synced} anime")

    return total_synced


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Script
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Run directly to populate the database from AniList.

    Usage:
        python -m utils.anilist                          # fetch top 200 popular
        python -m utils.anilist --mode top --pages 2     # fetch top 100 rated
        python -m utils.anilist --mode search --query "isekai"
        python -m utils.anilist --mode seasonal --season WINTER --year 2024
    """
    import argparse

    parser = argparse.ArgumentParser(description="Sync anime from AniList to Bingery DB")
    parser.add_argument("--mode", default="popular", choices=["popular", "top", "trending", "seasonal", "search"])
    parser.add_argument("--query", default="", help="Search query (for search mode)")
    parser.add_argument("--pages", type=int, default=4, help="Number of pages to fetch (50 per page)")
    parser.add_argument("--season", default=None, help="Season: WINTER, SPRING, SUMMER, FALL")
    parser.add_argument("--year", type=int, default=None, help="Season year (e.g. 2024)")
    args = parser.parse_args()

    from app import create_app

    app = create_app()

    print(f"\n{'═' * 50}")
    print(f"  Syncing from AniList (mode={args.mode})")
    print(f"{'═' * 50}\n")

    sync_anime_from_anilist(
        app,
        mode=args.mode,
        query=args.query,
        pages=args.pages,
        season=args.season,
        season_year=args.year,
    )

    print(f"\n{'═' * 50}")
    print(f"  Done!")
    print(f"{'═' * 50}\n")
