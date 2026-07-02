"""Chatbot route — provider-agnostic via utils.ai_provider."""
from __future__ import annotations

import json
import re
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from models import db, Anime
from utils.ai_provider import Message, ProviderUnavailableError, get_provider
from utils.ai_tools import ALL_TOOLS
from utils.nsfw import HARD_BLOCKED_GENRES, SOFT_BLOCKED_GENRES
from routes.chatbot_tools import BINGERY_SYSTEM, execute_tool, build_system_prompt
from routes.chat_context import build_llm_context


# Stripped from the response text — model often emits these but their IDs
# can't be trusted (the model hallucinates them). We resolve cards via the
# bold-title pattern below instead.
_ANIME_ID_RE = re.compile(r"\[ANIME_ID:\d+\]\s*")

# Bold titles in the model's reply: **Title** on a single line.
_BOLD_TITLE_RE = re.compile(r"\*\*([^*\n]{2,100}?)\*\*")

# Clickable option pills: [OPTIONS: a | b | c]. The model emits this when
# asking a multi-choice clarifying question; the frontend renders the pills.
_OPTIONS_RE = re.compile(r"\[OPTIONS:\s*([^\]\n]+?)\s*\]")

# Anime tagged with any of these are never surfaced as a card, period.
_CARD_BLOCKED_GENRES = set(HARD_BLOCKED_GENRES) | set(SOFT_BLOCKED_GENRES)


def _resolve_title(title: str) -> Anime | None:
    """Best-effort lookup: exact title or title_english match, else fuzzy
    substring match, ranked by api_score so popular entries win.
    """
    title = title.strip()
    if not title:
        return None
    # Exact match (case-insensitive) preferred.
    exact = (
        Anime.query.filter(
            db.or_(
                Anime.title.ilike(title),
                Anime.title_english.ilike(title),
            )
        )
        .order_by(Anime.api_score.desc().nullslast())
        .first()
    )
    if exact:
        return exact
    # Fuzzy substring fallback.
    return (
        Anime.query.filter(
            db.or_(
                Anime.title.ilike(f"%{title}%"),
                Anime.title_english.ilike(f"%{title}%"),
            )
        )
        .order_by(Anime.api_score.desc().nullslast())
        .first()
    )


def _extract_anime_refs(text: str):
    """Resolve the AI's recommendations into real anime cards.

    Strategy: ignore the model's hallucinated [ANIME_ID:N] markers and look
    up each **Title** mention in the DB by title. Hentai and Ecchi are
    always filtered out of the card list (the toggle controls *list* views,
    but card recommendations from chat are kept SFW unconditionally).
    """
    titles_in_order: list[str] = []
    seen_titles: set[str] = set()
    for m in _BOLD_TITLE_RE.finditer(text):
        t = m.group(1).strip()
        key = t.lower()
        if t and key not in seen_titles:
            seen_titles.add(key)
            titles_in_order.append(t)

    refs = []
    for t in titles_in_order:
        a = _resolve_title(t)
        if a is None:
            continue
        if any(g.name in _CARD_BLOCKED_GENRES for g in a.official_genres):
            continue
        refs.append({
            "id": a.id,
            "title": a.title_english or a.title,
            "image_url": a.image_url,
            "year": a.year,
            "genres": [g.name for g in a.official_genres[:3]],
        })

    # Strip stale ID markers from the prose; keep the bold formatting.
    cleaned = _ANIME_ID_RE.sub("", text).strip()
    return refs, cleaned


def _extract_options(text: str):
    """Return (options, cleaned_text).

    Primary: explicit [OPTIONS: a | b | c] marker. Smaller local models
    often ignore that instruction, so we also run a heuristic fallback
    that detects ``X or Y?`` and ``X, Y, or Z?`` patterns at the end of
    the assistant's reply.
    """
    options: list[str] = []
    m = _OPTIONS_RE.search(text)
    if m:
        raw = m.group(1)
        for part in raw.split("|"):
            p = part.strip()
            if p and len(p) <= 40:
                options.append(p)
    cleaned = _OPTIONS_RE.sub("", text).strip()

    if not options:
        options = _autofill_options_from_question(cleaned)

    return options[:5], cleaned


_LEADING_FILLER_RE = re.compile(
    r"^(?:something|more|a|an|the|maybe|perhaps|kinda|sort\s+of)\s+",
    re.IGNORECASE,
)


def _autofill_options_from_question(text: str) -> list[str]:
    """Heuristically pull options from a multi-choice question.

    Catches "Are you looking for grounded or magical?" and "Do you prefer
    dark and gritty, whimsical, or action-packed?" — returns [] for
    open-ended questions or anything that doesn't look like a clean choice.
    """
    body = text.rstrip()
    if not body.endswith("?"):
        return []
    body = body[:-1].rstrip()

    # Trim to the last clause — skip everything before an em-dash, colon,
    # or sentence boundary so we don't grab the verb phrase.
    for sep in ["—", "–", "—", "–", ":", ". ", "! ", "? "]:
        idx = body.rfind(sep)
        if idx != -1:
            body = body[idx + len(sep):]
            break

    if not re.search(r"\bor\b", body, flags=re.IGNORECASE):
        return []

    raw_chunks = [c.strip() for c in body.split(",") if c.strip()]
    expanded: list[str] = []
    for chunk in raw_chunks:
        for piece in re.split(r"\s+or\s+", chunk, flags=re.IGNORECASE):
            p = piece.strip(" .?!,")
            if p:
                expanded.append(p)

    seen: set[str] = set()
    out: list[str] = []
    for p in expanded:
        p = _LEADING_FILLER_RE.sub("", p).strip()
        if not p:
            continue
        if len(p) > 40 or len(p.split()) > 6:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)

    if not (2 <= len(out) <= 5):
        return []
    return out


chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chat")

MAX_TOOL_LOOPS = 5


def _optional_user_id() -> int | None:
    """Return the JWT user id if a valid token is present, otherwise None."""
    try:
        verify_jwt_in_request(optional=True)
    except NoAuthorizationError:
        return None
    ident = get_jwt_identity()
    return int(ident) if ident else None


@chatbot_bp.route("/message", methods=["POST"])
def chat_message():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "`message` is required"}), 400

    # The frontend hook posts `conversation`; older callers posted `history`.
    # Accept either so existing thread context isn't silently dropped.
    history = data.get("conversation") or data.get("history") or []
    # Frontend sends `mode`: "recommend" | "rate" | "onboard". Each mode
    # composes its own system prompt — see chatbot_tools.MODE_PROMPTS.
    mode = data.get("mode")
    user_id = _optional_user_id()

    messages: list[Message] = []
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        # Never accept system-role messages from the client — that would
        # let callers inject instructions above the real system prompt.
        if role in ("user", "assistant"):
            messages.append(Message(role=role, content=content))
    messages.append(Message(role="user", content=user_msg))

    system = build_system_prompt(mode)
    if user_id:
        system += f"\n\n[authenticated user id: {user_id}]"

    # Titles this conversation already suggested (assistant turns only —
    # a title the USER mentioned is fair game). Excluded from candidates,
    # from find_similar_anime results, and from the final card list so
    # "something else" actually produces something else.
    already_suggested: set[int] = set()
    for m in history:
        if m.get("role") == "assistant":
            for match in _BOLD_TITLE_RE.finditer(m.get("content") or ""):
                resolved = _resolve_title(match.group(1).strip())
                if resolved:
                    already_suggested.add(resolved.id)

    # Ground recommendations against the scored candidate set so the LLM
    # can't surface anime the user has already engaged with or the rec
    # engine has filtered out. Candidates are attached for authenticated
    # recommend mode; rate mode gets the full-signal user context without
    # candidates so scoring help is personally informed.
    candidate_ids: set[int] | None = None
    if user_id and mode in ("recommend", "rate"):
        context = build_llm_context(user_id, user_msg, mode, include_nsfw=False)
        if mode == "recommend":
            context["candidates"] = [
                c for c in context.get("candidates", [])
                if c["id"] not in already_suggested
            ]
            candidate_ids = {c["id"] for c in context["candidates"]}
        system += "\n\n# CONTEXT JSON\n" + json.dumps(context, ensure_ascii=False)
    if already_suggested:
        system += (
            "\n\nNever re-suggest a title you already recommended in this "
            "conversation unless the user asks about it by name."
        )

    provider = get_provider()

    try:
        for _ in range(MAX_TOOL_LOOPS):
            resp = provider.chat(messages=messages, tools=ALL_TOOLS, system=system)

            if resp.tool_calls:
                # Append the assistant's tool-use turn with the calls kept
                # structured — providers round-trip them in native format.
                messages.append(Message(
                    role="assistant",
                    content=resp.text or "",
                    tool_calls=resp.tool_calls,
                ))
                for call in resp.tool_calls:
                    arguments = call.arguments or {}
                    if call.name == "find_similar_anime" and already_suggested:
                        arguments = dict(arguments)
                        arguments["exclude_ids"] = sorted(
                            set(arguments.get("exclude_ids") or []) | already_suggested
                        )
                    # execute_tool already returns a JSON string.
                    result = execute_tool(call.name, arguments, user_id)
                    # Titles the similarity engine surfaced are grounded
                    # recommendations — let them pass the candidate
                    # validation even when outside the static top-40.
                    if call.name == "find_similar_anime" and candidate_ids is not None:
                        try:
                            payload = json.loads(result)
                            candidate_ids |= {
                                r["id"]
                                for r in payload.get("results", [])
                                if isinstance(r.get("id"), int)
                            }
                        except Exception:
                            pass
                    messages.append(Message(
                        role="tool",
                        tool_call_id=call.id,
                        tool_name=call.name,
                        content=result,
                    ))
                continue

            refs, cleaned = _extract_anime_refs(resp.text or "")
            # Validation pass: in grounded recommend mode, drop any resolved
            # anime that isn't in the scored candidate set (the LLM is told
            # to only PICK from `candidates`, but smaller local models drift).
            if candidate_ids is not None:
                refs = [r for r in refs if r["id"] in candidate_ids]
            # No-repeat guard: drop cards already suggested earlier in this
            # conversation, unless the user just asked about that title.
            if already_suggested:
                refs = [
                    r for r in refs
                    if r["id"] not in already_suggested
                    or r["title"].lower() in user_msg.lower()
                ]
            options, cleaned = _extract_options(cleaned)
            return jsonify({
                "response": cleaned,
                "suggested_anime": refs,
                "suggested_actions": options,
                "stop_reason": resp.stop_reason,
            })

        return jsonify({
            "response": "I kept reaching for tools but never settled. Try asking a narrower question.",
            "stop_reason": "loop_limit",
        })
    except ProviderUnavailableError as exc:
        # Home PC asleep / cloudflared tunnel down / CF Access rejecting.
        # Return a friendly 503 so the chat UI can show the offline state
        # instead of a generic 500.
        return jsonify({
            "response": (
                "The taste guide is offline right now — the home AI box "
                "looks asleep. Try again in a minute, or browse Discover "
                "while you wait."
            ),
            "suggested_anime": [],
            "suggested_actions": [],
            "stop_reason": "provider_unavailable",
            "error": str(exc),
        }), 503


@chatbot_bp.route("/quick-recommend", methods=["GET"])
@jwt_required()
def quick_recommend():
    user_id = int(get_jwt_identity())
    provider = get_provider()
    messages = [Message(
        role="user",
        content="Recommend one anime I would probably love based on my taste profile, in 2-3 sentences.",
    )]
    system = BINGERY_SYSTEM + f"\n\n[authenticated user id: {user_id}]"
    resp = provider.chat(messages=messages, tools=ALL_TOOLS, system=system)
    return jsonify({"response": resp.text})
