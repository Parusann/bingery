"""Single source of truth for AI tool definitions, provider-neutral."""
from utils.ai_provider import ToolSchema


SEARCH_ANIME_DATABASE = ToolSchema(
    name="search_anime_database",
    description=(
        "Search the local Bingery database for anime matching a title, genre, "
        "minimum score, or ordering. Use this when recommending anime that the "
        "user may have access to within the app."
    ),
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Substring to search for in titles."},
            "genre": {"type": "string", "description": "Official genre name."},
            "min_score": {"type": "number", "description": "Minimum community score (0–10)."},
            "sort": {
                "type": "string",
                "enum": ["score", "year", "popularity"],
                "description": "Sort order.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
    },
)

GET_USER_TASTE_PROFILE = ToolSchema(
    name="get_user_taste_profile",
    description=(
        "Return the logged-in user's top genres, average score, total rated "
        "count, and preferred year range. Use this before making personalized "
        "recommendations."
    ),
    parameters={"type": "object", "properties": {}},
)

GET_USER_WATCHLIST = ToolSchema(
    name="get_user_watchlist",
    description=(
        "Return the list of anime the user has already rated or added to their "
        "watchlist, so you can avoid recommending duplicates."
    ),
    parameters={"type": "object", "properties": {}},
)

GET_ANIME_DETAILS = ToolSchema(
    name="get_anime_details",
    description="Fetch full details on a specific anime by its Bingery database id.",
    parameters={
        "type": "object",
        "properties": {
            "anime_id": {"type": "integer", "description": "Internal database id."},
        },
        "required": ["anime_id"],
    },
)

SEARCH_ANILIST = ToolSchema(
    name="search_anilist",
    description=(
        "Search the live AniList GraphQL API for anime that are not yet in the "
        "local database. Use sparingly; prefer search_anime_database when possible."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-text search query."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
        },
        "required": ["query"],
    },
)

ALL_TOOLS: list[ToolSchema] = [
    SEARCH_ANIME_DATABASE,
    GET_USER_TASTE_PROFILE,
    GET_USER_WATCHLIST,
    GET_ANIME_DETAILS,
    SEARCH_ANILIST,
]

TOOL_NAMES: list[str] = [t.name for t in ALL_TOOLS]
