"""Public waitlist endpoint — records an email and sends a confirmation."""
import logging
import re

from flask import Blueprint, request, jsonify

from models import db, Waitlist
from utils.email_provider import get_email_provider

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
