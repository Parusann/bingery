"""Waitlist endpoints.

Public: POST /api/waitlist records an email and sends a confirmation.
Owner-only (JWT + OWNER_EMAIL match): GET  /api/waitlist/admin lists every
entry; POST /api/waitlist/admin/<id>/approve mints a one-time invite code,
emails it to the person, and marks the entry approved.
"""
import logging
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from models import db, User, Waitlist
from utils.email_provider import EmailSendError, get_email_provider

logger = logging.getLogger(__name__)

waitlist_bp = Blueprint("waitlist", __name__)

# Deliberately permissive: one @, a dot in the domain, no spaces. Real
# validity is proven by the confirmation email actually arriving.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@waitlist_bp.route("", methods=["POST"])
def join_waitlist():
    data = request.get_json(silent=True) or {}
    email_raw = data.get("email")
    if not isinstance(email_raw, str):
        return jsonify({"error": "Please enter a valid email address."}), 400
    email = email_raw.strip().lower()
    if not email or len(email) > 120 or not _EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    if db.session.query(Waitlist).filter_by(email=email).first() is not None:
        return jsonify({"status": "already"}), 200

    db.session.add(Waitlist(email=email))
    db.session.commit()

    # Best-effort sends: neither a failing email nor a misconfigured
    # provider must lose the recorded signup, and one email failing must
    # not block the other.
    provider = None
    try:
        provider = get_email_provider()
    except Exception:
        logger.exception(
            "email provider unavailable; skipping waitlist emails for %s", email
        )
    if provider is not None:
        try:
            provider.send_waitlist_confirmation(email)
        except Exception:
            logger.exception("waitlist confirmation email failed for %s", email)
        try:
            provider.send_waitlist_owner_alert(email)
        except Exception:
            logger.exception("waitlist owner alert failed for %s", email)

    return jsonify({"status": "added"}), 200


# ─── Owner-only admin endpoints ──────────────────────────────────────────────

def _is_owner() -> bool:
    """True iff the JWT belongs to the solo-owner account (OWNER_EMAIL)."""
    user = db.session.get(User, int(get_jwt_identity()))
    return user is not None and user.email == current_app.config.get("OWNER_EMAIL")


def _signup_base_url() -> str:
    """Public origin for the invite email's signup link.

    Production sets CORS_ORIGINS to the real site origin (required by the
    config boot guard), so reuse it; dev falls back to this request's host.
    """
    for origin in current_app.config.get("CORS_ORIGINS") or []:
        if origin and origin != "*":
            return origin.rstrip("/")
    return request.host_url.rstrip("/")


@waitlist_bp.route("/admin", methods=["GET"])
@jwt_required()
def admin_list():
    if not _is_owner():
        return jsonify({"error": "Not authorized."}), 403
    entries = db.session.query(Waitlist).order_by(Waitlist.created_at.desc()).all()
    return jsonify({"entries": [e.to_dict() for e in entries]}), 200


@waitlist_bp.route("/admin/<int:entry_id>/approve", methods=["POST"])
@jwt_required()
def admin_approve(entry_id: int):
    if not _is_owner():
        return jsonify({"error": "Not authorized."}), 403
    entry = db.session.get(Waitlist, entry_id)
    if entry is None:
        return jsonify({"error": "No such waitlist entry."}), 404
    if entry.status != "pending":
        return jsonify({"error": f"This entry is already {entry.status}."}), 409

    # ~128-bit urlsafe token: unguessable, and bound to this entry's email
    # by the register gate (routes/auth.py).
    code = secrets.token_urlsafe(16)
    entry.invite_code = code
    entry.status = "approved"
    entry.approved_at = datetime.now(timezone.utc)

    query = urlencode({"invite": code, "email": entry.email})
    signup_url = f"{_signup_base_url()}/auth?{query}"
    try:
        get_email_provider().send_waitlist_invite(entry.email, code, signup_url)
    except EmailSendError:
        # Unlike the best-effort join emails, the invite IS the deliverable:
        # roll back so a failed send leaves the entry pending and retryable
        # (a fresh code is minted on the retry).
        db.session.rollback()
        logger.exception("waitlist invite email failed for %s", entry.email)
        return (
            jsonify({"error": "Couldn't send the invite email. Nothing was changed — try again."}),
            503,
        )

    db.session.commit()
    return jsonify({"entry": entry.to_dict()}), 200
