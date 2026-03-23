"""
Bingery AI Chatbot — powered by Claude (Anthropic API).

Features:
- Personality-driven conversational recommendations
- Accesses user's watchlist/taste profile for personalized suggestions
- Searches local DB and AniList for anime research
- AI-assisted rating helper
- Onboarding assistant for new users
"""

import json
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from models import db, Anime, Rating, FanGenreVote, Genre, anime_genres
from routes.recommend import build_taste_profile

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chat")

# ═══════════════════════════════════════════════════════════════════════════════
# BINGERY AI SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS for Claude
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "search_anime_database",
        "description": "Search the Bingery anime database by title, genre, or criteria. Returns matching anime with scores, genres, and fan genre data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query — a title, genre name, or description"},
                "genre": {"type": "string", "description": "Filter by official genre name (e.g. 'Action', 'Mystery')"},
                "min_score": {"type": "number", "description": "Minimum API score (0-10)"},
                "sort_by": {"type": "string", "enum": ["score", "year", "popularity"], "description": "How to sort results"},
                "limit": {"type": "integer", "description": "Max results to return (default 10)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_user_taste_profile",
        "description": "Get the current user's taste profile including their top genres, average score, number of anime rated, and rating patterns. Use this to personalize recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_user_watchlist",
        "description": "Get the list of anime the user has rated, including their scores and genre votes. Use this to avoid recommending anime they've already seen and to understand their preferences.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 50)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_anime_details",
        "description": "Get full details about a specific anime by its database ID, including synopsis, community score, fan genres, and all metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "anime_id": {"type": "integer", "description": "The Bingery database ID of the anime"},
            },
            "required": ["anime_id"],
        },
    },
    {
        "name": "search_anilist",
        "description": "Search AniList for anime that might not be in Bingery's database yet. Good for finding newer or niche titles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

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
            Rating.query.filter_by(user_id=user_id)
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
        anime = Anime.query.get(anime_id) if anime_id else None
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


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@chatbot_bp.route("/message", methods=["POST"])
def chat_message():
    """
    POST /api/chat/message
    Body: {
        "message": "I want a dark mystery anime",
        "conversation": [...previous messages...],
        "mode": "recommend" | "rate" | "onboard"
    }

    The conversation array uses Anthropic's message format:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    """
    import anthropic

    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "Anthropic API key not configured. Set ANTHROPIC_API_KEY in your environment."}), 500

    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    conversation = data.get("conversation", [])
    mode = data.get("mode", "recommend")

    if not user_message:
        return jsonify({"error": "Message is required."}), 400

    # Check if user is logged in (optional)
    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            user_id = int(uid)
    except Exception:
        pass

    # Build system prompt with mode context
    system = BINGERY_SYSTEM
    if mode == "rate":
        system += "\n\nYou are currently in RATING ASSISTANT MODE. Help the user rate an anime they've watched. Be conversational about it — discuss their experience, suggest a score, and suggest fan genre tags."
    elif mode == "onboard":
        system += "\n\nYou are currently in ONBOARDING MODE. This is a new user. Be extra welcoming! Ask fun questions to learn their taste and suggest initial anime to get them started."

    if user_id:
        system += f"\n\nThe user is logged in (user_id: {user_id}). You can use tools to access their taste profile and watchlist."
    else:
        system += "\n\nThe user is not logged in. You cannot access personalized data but can still make great recommendations."

    # Build messages
    messages = []
    for msg in conversation:
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Call Claude with tool use
    client = anthropic.Anthropic(api_key=api_key)

    try:
        # Agentic loop: keep calling until Claude gives a final text response
        max_turns = 5
        for _ in range(max_turns):
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=system,
                tools=TOOLS,
                messages=messages,
            )

            # Check if there are tool uses
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                # Final response — extract text
                text_parts = [b.text for b in response.content if b.type == "text"]
                final_text = "\n".join(text_parts)

                # Extract anime IDs mentioned (for frontend linking)
                import re
                anime_refs = re.findall(r'\[ANIME_ID:(\d+)\]', final_text)
                # Clean the ID tags from display text
                clean_text = re.sub(r'\[ANIME_ID:\d+\]\s*', '', final_text)

                # Fetch image data for referenced anime
                anime_cards = []
                for aid_str in anime_refs:
                    try:
                        anime = Anime.query.get(int(aid_str))
                        if anime:
                            anime_cards.append({
                                "id": anime.id,
                                "title": anime.title_english or anime.title,
                                "image_url": anime.image_url,
                                "api_score": anime.api_score,
                                "community_score": anime.get_community_score(),
                                "year": anime.year,
                                "episodes": anime.episodes,
                                "genres": [g.name for g in anime.official_genres][:3],
                            })
                    except Exception:
                        pass

                return jsonify({
                    "response": clean_text,
                    "anime_cards": anime_cards,
                    "stop_reason": response.stop_reason,
                }), 200

            # Process tool calls
            # Add assistant message with tool use blocks
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool and add results
            tool_results = []
            for tool_use in tool_uses:
                result = execute_tool(tool_use.name, tool_use.input, user_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

        # If we hit max turns, return what we have
        return jsonify({
            "response": "I got a bit carried away researching! Let me give you a quick answer based on what I found. Could you try asking again with a more specific request?",
            "anime_cards": [],
            "stop_reason": "max_turns",
        }), 200

    except anthropic.APIError as e:
        return jsonify({"error": f"AI service error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500


@chatbot_bp.route("/quick-recommend", methods=["GET"])
def quick_recommend():
    """
    GET /api/chat/quick-recommend?mood=dark&genres=Horror,Mystery
    Fast non-AI recommendations for when the API key isn't set.
    """
    mood = request.args.get("mood", "").lower()
    genres_param = request.args.get("genres", "")
    genres = [g.strip() for g in genres_param.split(",") if g.strip()]
    limit = min(request.args.get("limit", 6, type=int), 20)

    query = Anime.query.filter(Anime.api_score.isnot(None))

    if genres:
        query = query.join(anime_genres).join(Genre).filter(Genre.name.in_(genres))

    if mood in ("dark", "intense", "mature"):
        query = query.join(anime_genres).join(Genre).filter(
            Genre.name.in_(["Horror", "Thriller", "Mystery", "Drama"])
        )
    elif mood in ("fun", "light", "happy", "wholesome"):
        query = query.join(anime_genres).join(Genre).filter(
            Genre.name.in_(["Comedy", "Slice of Life", "Romance"])
        )

    results = query.order_by(Anime.api_score.desc()).distinct().limit(limit).all()

    return jsonify({
        "recommendations": [a.to_dict(include_community=True) for a in results],
    }), 200
