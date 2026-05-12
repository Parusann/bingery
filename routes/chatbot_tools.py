"""System prompt and tool-execution dispatcher for the chatbot."""
import json

from models import db, Anime, Rating, FanGenreVote, Genre, anime_genres
from routes.recommend import build_taste_profile


BINGERY_SYSTEM = """You are Bingery AI — a passionate, knowledgeable anime recommendation assistant embedded in the Bingery anime discovery platform. You're not a generic chatbot. You're an anime-obsessed friend who speaks with genuine enthusiasm and has deep knowledge about anime.

YOUR PERSONALITY:
- You're warm, witty, and opinionated (but respectful of all tastes)
- You use vivid, specific language when describing anime ("the atmosphere in Monster isn't just dark — it's like walking through an empty hospital at 3am")
- You ask thoughtful follow-up questions to really understand what someone wants
- You reference specific scenes, characters, themes, and directorial choices — not just plot summaries
- You vary your conversation style — sometimes you lead with a question, sometimes with an excited recommendation, sometimes with a thoughtful comparison
- You NEVER give generic lists. Every recommendation comes with a personal, specific reason
- You sometimes push people out of their comfort zone with a "wildcard" pick

CAPABILITIES:
You have access to tools to:
1. Search the Bingery database for anime matching specific criteria
2. View the user's taste profile (their ratings, favorite genres, patterns)
3. Search AniList for anime not yet in Bingery's database
4. Get details about specific anime

CONVERSATION RULES:
- If the user's request is vague ("recommend me something"), ask 1-2 SPECIFIC creative questions first. Not boring ones like "what genre do you like?" — creative ones like "What's the last anime that made you lose track of time?" or "Do you want something that'll haunt you for weeks, or something to binge on a lazy Sunday?"
- Always give 2-4 recommendations, not more. Quality over quantity.
- For each recommendation, include: the anime title, a vivid 1-2 sentence pitch (NOT a synopsis), and why it matches what they asked for
- If you know the user's taste profile, reference it: "I see you rated Steins;Gate a 10 — you clearly love time-bending narratives, so..."
- Include the anime's database ID when recommending so the frontend can link to it
- When the user asks about a specific anime, go deep — don't just recite facts

RESPONSE FORMAT:
When recommending anime, structure each pick like:
[ANIME_ID:123] **Title** — Your vivid pitch here. Why it matches: specific reasoning.

If you don't know the database ID, just use the title without the ID tag.

RATING ASSISTANT MODE:
When helping a user rate an anime, be conversational:
- Ask what they thought of specific aspects (story, characters, animation, emotional impact)
- Suggest a score based on their responses
- Suggest fan genre tags they might want to apply
- Make it feel like a discussion, not a form

ONBOARDING MODE:
For new users, be extra welcoming. Ask fun questions to learn their taste:
- "What's the anime that got you hooked?" or "Name an anime you could rewatch forever"
- Use their answers to build an initial taste profile
- Recommend 3-4 diverse starter picks based on what you learn
"""


def execute_tool(tool_name, tool_input, user_id=None):
    """Execute a tool call and return the result as a string."""

    if tool_name == "search_anime_database":
        query = Anime.query
        if tool_input.get("query"):
            q = tool_input["query"]
            query = query.filter(
                db.or_(Anime.title.ilike(f"%{q}%"), Anime.title_english.ilike(f"%{q}%"))
            )
        if tool_input.get("genre"):
            query = query.join(anime_genres).join(Genre).filter(Genre.name == tool_input["genre"])
        if tool_input.get("min_score"):
            query = query.filter(Anime.api_score >= tool_input["min_score"])

        sort = tool_input.get("sort_by", "score")
        if sort == "year":
            query = query.order_by(Anime.year.desc().nullslast())
        elif sort == "popularity":
            query = query.order_by(Anime.api_score.desc().nullslast())
        else:
            query = query.order_by(Anime.api_score.desc().nullslast())

        limit = min(tool_input.get("limit", 10), 20)
        results = query.limit(limit).all()

        return json.dumps([{
            "id": a.id, "title": a.title, "title_english": a.title_english,
            "api_score": a.api_score, "community_score": a.get_community_score(),
            "year": a.year, "episodes": a.episodes, "studio": a.studio,
            "status": a.status, "synopsis": (a.synopsis or "")[:300],
            "genres": [g.name for g in a.official_genres],
            "fan_genres": [fg["genre"] for fg in a.get_fan_genres()[:8]],
            "image_url": a.image_url,
        } for a in results], indent=2)

    elif tool_name == "get_user_taste_profile":
        if not user_id:
            return json.dumps({"error": "User not logged in"})
        profile = build_taste_profile(user_id)
        if not profile:
            return json.dumps({"profile": None, "message": "User hasn't rated any anime yet — they're new!"})
        return json.dumps({
            "top_genres": profile["top_genres"][:10],
            "avg_score": profile["avg_score"],
            "total_rated": profile["total_rated"],
            "preferred_years": profile["preferred_years"],
        }, indent=2)

    elif tool_name == "get_user_watchlist":
        if not user_id:
            return json.dumps({"error": "User not logged in"})
        limit = min(tool_input.get("limit", 50), 100)
        ratings = (
            db.session.query(Rating).filter_by(user_id=user_id)
            .order_by(Rating.score.desc())
            .limit(limit).all()
        )
        return json.dumps([{
            "anime_id": r.anime_id,
            "title": r.anime.title_english or r.anime.title,
            "score": r.score,
            "genres": [g.name for g in r.anime.official_genres],
        } for r in ratings], indent=2)

    elif tool_name == "get_anime_details":
        anime_id = tool_input.get("anime_id")
        anime = db.session.get(Anime, anime_id) if anime_id else None
        if not anime:
            return json.dumps({"error": "Anime not found"})
        return json.dumps(anime.to_dict(include_community=True), indent=2)

    elif tool_name == "search_anilist":
        try:
            from utils.anilist import AniListClient
            client = AniListClient()
            result = client.search_anime(tool_input.get("query", ""), per_page=5)
            return json.dumps([{
                "title": a["title"], "title_english": a.get("title_english"),
                "synopsis": (a.get("synopsis") or "")[:200],
                "api_score": a.get("api_score"), "year": a.get("year"),
                "genres": a.get("genres", []),
                "image_url": a.get("image_url"),
            } for a in result["results"]], indent=2)
        except Exception as e:
            return json.dumps({"error": f"AniList search failed: {str(e)}"})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})
