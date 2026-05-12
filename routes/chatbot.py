"""Chatbot route — provider-agnostic via utils.ai_provider."""
from __future__ import annotations

import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import NoAuthorizationError

from utils.ai_provider import Message, get_provider
from utils.ai_tools import ALL_TOOLS
from routes.chatbot_tools import execute_tool, BINGERY_SYSTEM


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

    history = data.get("history") or []
    user_id = _optional_user_id()

    messages: list[Message] = []
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant", "system"):
            messages.append(Message(role=role, content=content))
    messages.append(Message(role="user", content=user_msg))

    system = BINGERY_SYSTEM
    if user_id:
        system += f"\n\n[authenticated user id: {user_id}]"

    provider = get_provider()

    for _ in range(MAX_TOOL_LOOPS):
        resp = provider.chat(messages=messages, tools=ALL_TOOLS, system=system)

        if resp.tool_calls:
            # Append the assistant's tool-use turn.
            messages.append(Message(
                role="assistant",
                content=json.dumps([
                    {"name": c.name, "arguments": c.arguments, "id": c.id}
                    for c in resp.tool_calls
                ]),
            ))
            for call in resp.tool_calls:
                result = execute_tool(call.name, call.arguments, user_id)
                messages.append(Message(
                    role="tool",
                    tool_call_id=call.id,
                    tool_name=call.name,
                    content=json.dumps(result),
                ))
            continue

        return jsonify({
            "response": resp.text,
            "stop_reason": resp.stop_reason,
        })

    return jsonify({
        "response": "I kept reaching for tools but never settled. Try asking a narrower question.",
        "stop_reason": "loop_limit",
    })


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
