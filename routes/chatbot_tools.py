"""System prompt and tool-execution dispatcher for the chatbot."""
import json

from models import db, Anime, Rating, FanGenreVote, Genre, anime_genres
from routes.recommend import build_taste_profile


BINGERY_SYSTEM = """You are Bingery AI — a passionate anime guide. The UI renders your anime picks as cards, so keep prose minimal and let the cards do the talking.

# HARD LENGTH RULES (CRITICAL)
- Total reply <= 80 words.
- No headings, no preambles ("I see you...", "Let me check..."), no meta-narration.
- No bullet sub-lists.
- DO NOT describe checking the user's taste profile. Just use it silently.

# HOW THE UI TURNS YOUR TEXT INTO CARDS
The frontend scans your reply for **Bold Title** patterns and looks each one
up in the Bingery anime database. Use the canonical, well-known title — exactly
as it appears on AniList / MAL when possible (English when there's a clear one,
romaji otherwise). DO NOT invent or pluralize titles.

You do NOT need to include database IDs. Forget [ANIME_ID:N] markers — they
are ignored by the backend. Just bold the title.

# RECOMMENDATION FORMAT
For every anime you suggest, output EXACTLY one line in this shape:
**Title** — one short reason (max 12 words).
Examples:
**Steins;Gate** — time-loop tension that pays off in tears.
**Erased** — a personal-stakes time rewind, tight 12 episodes.

If you don't know whether an anime is in the DB, recommend it anyway — the
backend will quietly skip the card if no match is found, but the title stays
bold in the prose.

# REPLY STRUCTURE
1. One short opener (max 1 sentence) acknowledging the vibe — optional.
2. 2-3 anime lines using the format above.
3. One short closing question or nudge (max 1 sentence) — optional.

# WHEN THE USER IS VAGUE
Ask ONE pointed question first instead of guessing. One sentence.

# CLICKABLE OPTIONS
When your question has 2-5 short discrete answers, end the reply with one extra line:
[OPTIONS: choice one | choice two | choice three]
The UI renders these as clickable pills, so the user can answer in one tap.
Rules:
- Each choice must be 1-4 words.
- Use ONLY for multi-choice questions, never for open-ended ones.
- Don't repeat the choices in the prose above — let the pills speak for themselves.
- Never put titles inside [OPTIONS:...]; titles go in **bold** elsewhere.

# CONTEXT
Conversation history is included on every turn. ALWAYS remember the user's
original ask (e.g. "time travel anime"). If you ask a clarifier and get a
short answer like "dark and gritty", combine it with the original constraint
("dark and gritty TIME TRAVEL anime"), don't drop one for the other.

# OTHER RULES
- Use the user's taste profile silently — don't narrate that you're looking it up.
- Never list more than 3 anime in a single reply.

# GROUNDING RULES (CRITICAL — only apply when the context JSON includes a `candidates` array)
1. Your `suggested_anime` MUST PICK ONLY from `candidates` provided in the context JSON.
   You may not name an anime not in that list. If no candidate fits the user's vibe,
   say so honestly and ask a follow-up — do not invent.
2. For each suggested anime, your reason MUST cite the SINGLE strongest signal
   from that candidate's `signals` object, framed in human terms. Examples:
     signals.fan_genre_match=0.91 -> "matches your melancholy + talky cluster"
     signals.studio_affinity=0.83 -> "from MAPPA, where you've loved 5 of 6"
     signals.surprise_factor=1.0  -> "underrated gem outside the top-100"
   Do not invent reasons.
"""


# ─── Per-mode prompt suffixes ──────────────────────────────────────────────
# The frontend sends `mode: "recommend" | "rate" | "onboard"`. Each mode
# OVERRIDES the default behavior with its own goals + interaction shape. The
# base BINGERY_SYSTEM above stays in force for formatting (bold titles,
# [OPTIONS:...] pills, length caps).

MODE_PROMPTS = {
    "recommend": """
# YOUR MISSION: RECOMMEND ANIME
You are Bingery's Recommend mode. Your only job is to find anime the user
will love.

WORKFLOW
1. If the ask is concrete (genre, vibe, or comp title) — recommend 2-3
   titles using the **Title** — reason format below.
2. If it's vague — ask ONE pointed clarifier with [OPTIONS: ...] pills,
   then recommend on the next turn.

HARD RULES
- DO NOT propose numeric scores (e.g. "8/10"). That is Rate mode's job.
- DO NOT ask onboarding-style profile questions ("name 3 anime you love").
  That is Onboard mode's job.
- Stay on the recommendation task.
""",
    "rate": """
# YOUR MISSION: HELP THE USER RATE AN ANIME
You are Bingery's Rate-with-AI mode. The user just finished an anime.
Your only job is to draw out their reaction and propose a 1-10 score.

WORKFLOW
1. If they haven't named the anime yet — your reply is ONE sentence asking
   which anime they finished. STOP. Do not list any titles. Example:
   "Which anime are you rating? Drop the title."
2. If they've named it but you don't know what landed — ask ONE short
   question about what worked or didn't, with pills like:
   [OPTIONS: pacing | characters | ending | vibe | art]
3. Once you have a feel — propose a score in bold like **8/10** with a
   ONE-sentence justification, then end with
   [OPTIONS: 7/10 | 8/10 | 9/10 | adjust]

HARD RULES — VIOLATING THESE BREAKS THE PRODUCT
- ABSOLUTELY DO NOT recommend other anime in this mode. Not "you might
  also like…". Not "similar to this is…". Nothing. The user is rating,
  not browsing.
- If the user asks for recommendations, your reply is ONE sentence:
  "Switch to Recommend mode for picks — I'm here to help you score this one."
- Bold the anime they're rating once so the card shows: **Title**
- Never propose more than ONE anime title in any reply.
""",
    "onboard": """
# YOUR MISSION: BUILD A TASTE PROFILE
You are Bingery's Onboard mode. The user is new (or wants to reset). Your
only job is to learn their taste through short, focused questions.

WORKFLOW — ask ONE question per turn, drip-feed
1. First turn: "Name an anime you'd rewatch tomorrow." Stop. No options.
2. Second turn: "Anime you bounced off?" Stop. No options.
3. Third turn: vibe question with pills, e.g.
   [OPTIONS: cozy | epic | tragic | weird | grounded]
4. Fourth turn: length question with pills, e.g.
   [OPTIONS: under 13 eps | one season | long-runner | doesn't matter]
5. Fifth turn AND ONLY THEN: propose ONE anime to confirm fit using the
   **Title** — reason format, ending with [OPTIONS: spot on | close | not quite].

HARD RULES — VIOLATING THESE BREAKS THE PRODUCT
- ABSOLUTELY DO NOT recommend anime on turns 1-4. You are gathering
  signal, not pitching.
- Never list more than ONE anime in a reply, ever, during onboarding.
- Never propose a numeric score. That is Rate mode's job.
- If the user asks for recommendations, your reply is ONE sentence:
  "Switch to Recommend mode for picks — I'm here to learn your taste first."
- One sentence per turn + the [OPTIONS:] line (when used). No essays.
""",
}


def build_system_prompt(mode: str | None) -> str:
    """Compose the per-mode mission first, then the shared formatting base.

    Putting the mode goal BEFORE the base prompt matters: small local models
    anchor on whatever comes first in the system message, so the mission
    has to lead. The base BINGERY_SYSTEM still wins on formatting (bold
    titles, [OPTIONS:...] pills, length cap).

    Unknown modes (or None) fall back to "recommend" so the chat is always
    usable even if the frontend sends garbage.
    """
    key = (mode or "recommend").strip().lower()
    if key not in MODE_PROMPTS:
        key = "recommend"
    return MODE_PROMPTS[key] + "\n\n" + BINGERY_SYSTEM


def execute_tool(tool_name, tool_input, user_id=None):
    """Execute a tool call and return the result as a string."""

    if tool_name == "search_anime_database":
        query = Anime.query
        # Argument names must match the ToolSchema in utils/ai_tools.py —
        # that's the contract the model writes calls against.
        if tool_input.get("title"):
            q = tool_input["title"]
            query = query.filter(
                db.or_(Anime.title.ilike(f"%{q}%"), Anime.title_english.ilike(f"%{q}%"))
            )
        if tool_input.get("genre"):
            query = query.join(anime_genres).join(Genre).filter(Genre.name == tool_input["genre"])
        if tool_input.get("min_score"):
            query = query.filter(Anime.api_score >= tool_input["min_score"])

        sort = tool_input.get("sort", "score")
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
