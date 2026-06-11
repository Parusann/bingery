import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from models import db, PendingSignup, User
from utils.email_provider import EmailSendError, get_email_provider

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
bcrypt = Bcrypt()

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_RESENDS = 5
PENDING_MAX_AGE = timedelta(hours=24)


def _utcnow() -> datetime:
    """Naive UTC now. SQLite hands back naive datetimes, so all
    pending-signup time math stays naive-to-naive. Module-level so tests
    can monkeypatch the clock."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    # ── Validate ──────────────────────────────────────────────────────────
    errors = []
    if not data.get("username") or len(data["username"].strip()) < 3:
        errors.append("Username must be at least 3 characters.")
    if not data.get("email") or "@" not in data.get("email", ""):
        errors.append("A valid email is required.")
    if not data.get("password") or len(data["password"]) < 6:
        errors.append("Password must be at least 6 characters.")
    if errors:
        return jsonify({"error": errors}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()

    if db.session.query(User).filter_by(username=username).first():
        return jsonify({"error": "Username already taken."}), 409
    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    now = _utcnow()

    # ── Lazy purge of abandoned signups ──────────────────────────────────
    db.session.query(PendingSignup).filter(
        PendingSignup.created_at < now - PENDING_MAX_AGE
    ).delete()

    display_name_raw = data.get("display_name")
    display_name = (
        display_name_raw.strip()[:80] if isinstance(display_name_raw, str) and display_name_raw.strip()
        else None
    )

    # ── Upsert the pending signup (re-register overwrites: the previous
    #    holder never proved ownership of this email) ──────────────────────
    code = _generate_code()
    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    if pending is None:
        pending = PendingSignup(email=email, created_at=now)
        db.session.add(pending)
    else:
        pending.created_at = now
    pending.username = username
    pending.password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    pending.display_name = display_name
    pending.code_hash = bcrypt.generate_password_hash(code).decode("utf-8")
    pending.code_expires_at = now + CODE_TTL
    pending.attempts_remaining = 5
    pending.resend_count = 0
    pending.last_sent_at = now

    try:
        get_email_provider().send_verification_code(email, code)
    except EmailSendError:
        db.session.commit()  # keep the pending row; the user can retry
        return (
            jsonify({"error": "Couldn't send the verification email. Please try again."}),
            503,
        )

    db.session.commit()
    return jsonify({"verification_required": True, "email": email}), 202


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = db.session.query(User).filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password."}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict(include_stats=True)}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_profile():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"user": user.to_dict(include_stats=True)}), 200


@auth_bp.route("/me", methods=["PATCH"])
@jwt_required()
def update_profile():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json() or {}
    if "username" in data and data["username"].strip():
        existing = db.session.query(User).filter_by(username=data["username"].strip()).first()
        if existing and existing.id != user.id:
            return jsonify({"error": "Username already taken."}), 409
        user.username = data["username"].strip()
    if "bio" in data:
        user.bio = (data["bio"] or "")[:500]
    if "avatar_url" in data:
        user.avatar_url = data["avatar_url"]
    if "display_name" in data:
        dn = data["display_name"]
        user.display_name = dn.strip()[:80] if isinstance(dn, str) and dn.strip() else None

    db.session.commit()
    return jsonify({"user": user.to_dict(include_stats=True)}), 200
