import os
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from models import db, PendingSignup, User, Waitlist
from utils.email_provider import CODE_TTL_MINUTES, EmailSendError, get_email_provider

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
bcrypt = Bcrypt()

CODE_TTL = timedelta(minutes=CODE_TTL_MINUTES)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_RESENDS = 5
PENDING_MAX_AGE = timedelta(hours=24)

# Burned on the no-pending paths of verify()/resend() so their timing
# matches the real-work paths (anti-enumeration).
_DUMMY_CODE_HASH = bcrypt.generate_password_hash("000000").decode("utf-8")


def _utcnow() -> datetime:
    """Naive UTC now. SQLite hands back naive datetimes, so all
    pending-signup time math stays naive-to-naive. Module-level so tests
    can monkeypatch the clock."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    # ── Validate (types first: non-string JSON values must 400, not 500;
    #    length caps match the column sizes so Postgres can't 500) ────────
    errors = []
    username_raw = data.get("username")
    email_raw = data.get("email")
    password_raw = data.get("password")
    if not isinstance(username_raw, str) or len(username_raw.strip()) < 3:
        errors.append("Username must be at least 3 characters.")
    elif len(username_raw.strip()) > 80:
        errors.append("Username must be at most 80 characters.")
    if not isinstance(email_raw, str) or "@" not in email_raw:
        errors.append("A valid email is required.")
    elif len(email_raw.strip()) > 120:
        errors.append("Email must be at most 120 characters.")
    if not isinstance(password_raw, str) or len(password_raw) < 6:
        errors.append("Password must be at least 6 characters.")
    if errors:
        return jsonify({"error": " ".join(errors)}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()

    # ── Per-person invite gate ────────────────────────────────────────────
    # Registration requires the one-time code minted when the owner approved
    # this email's waitlist entry (routes/waitlist.py). The code is bound to
    # the entry's email and consumed at verify. SIGNUP_OPEN=1 bypasses the
    # gate for dev/tests only — production refuses to boot with it set
    # (config.py). Read live so tests can toggle it per-test.
    if os.environ.get("SIGNUP_OPEN", "").strip().lower() not in ("1", "true", "yes"):
        provided_raw = data.get("invite_code")
        provided = provided_raw.strip() if isinstance(provided_raw, str) else ""
        entry = db.session.query(Waitlist).filter_by(email=email).first()
        if entry is None or not entry.invite_code:
            return jsonify(
                {
                    "error": "Sign-ups are invite-only right now. Join the "
                    "waitlist and you'll receive a personal invite code by "
                    "email once you're approved."
                }
            ), 403
        if not provided or not secrets.compare_digest(entry.invite_code, provided):
            return jsonify(
                {
                    "error": "That invite code doesn't match this email "
                    "address. Use the code from your invite email, with the "
                    "email address it was sent to."
                }
            ), 403
        if entry.code_used_at is not None:
            return jsonify(
                {"error": "This invite code has already been used."}
            ), 403

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
    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    if pending is not None and now - pending.last_sent_at < RESEND_COOLDOWN:
        # Same cooldown as /resend — an unauthenticated register loop must
        # not become an email cannon. Keep the already-emailed code valid,
        # but apply the latest identity fields so a quick "fix my typo"
        # re-submit still wins when the user verifies.
        pending.username = username
        pending.password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
        pending.display_name = display_name
        pending.created_at = now
        db.session.commit()
        return jsonify({"verification_required": True, "email": email}), 202

    code = _generate_code()
    password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    if pending is None:
        pending = PendingSignup(email=email, created_at=now)
        db.session.add(pending)
    else:
        pending.created_at = now
    pending.username = username
    pending.password_hash = password_hash
    pending.display_name = display_name
    pending.code_hash = bcrypt.generate_password_hash(code).decode("utf-8")
    pending.code_expires_at = now + CODE_TTL
    pending.attempts_remaining = 5
    pending.resend_count = 0
    pending.last_sent_at = now

    try:
        get_email_provider().send_verification_code(email, code)
    except EmailSendError:
        # Roll back so a failed send never replaces a previously emailed
        # (still valid) code or starts a cooldown for an email that never
        # went out — mirrors the /resend failure path.
        db.session.rollback()
        return (
            jsonify({"error": "Couldn't send the verification email. Please try again."}),
            503,
        )

    try:
        db.session.commit()
    except IntegrityError:
        # Two simultaneous registrations for the same email: the loser's
        # INSERT collides on the unique email. The winner's code was already
        # emailed to this same address, so keep it valid and apply the latest
        # identity fields — the same semantics as the cooldown branch above.
        db.session.rollback()
        winner = db.session.query(PendingSignup).filter_by(email=email).first()
        if winner is None:
            return jsonify({"error": "Something went wrong. Please try again."}), 503
        winner.username = username
        winner.password_hash = password_hash
        winner.display_name = display_name
        winner.created_at = now
        db.session.commit()
    return jsonify({"verification_required": True, "email": email}), 202


@auth_bp.route("/verify", methods=["POST"])
def verify():
    """Exchange a pending signup + correct code for a real account + JWT.

    Every failure mode (unknown email, expired, attempts exhausted, wrong
    code) returns the same body so nothing is leaked about which it was.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()
    uniform = jsonify({"error": "Invalid or expired code."}), 400

    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    if not pending or not code:
        # Anti-timing-oracle: cost one bcrypt check like the wrong-code
        # path below, so timing doesn't reveal whether a pending exists.
        bcrypt.check_password_hash(_DUMMY_CODE_HASH, code or "000000")
        return uniform

    now = _utcnow()
    if now > pending.code_expires_at or pending.attempts_remaining <= 0:
        return uniform

    if not bcrypt.check_password_hash(pending.code_hash, code):
        # Atomic decrement: the WHERE predicate stops concurrent wrong
        # attempts from stretching the budget via lost updates.
        db.session.query(PendingSignup).filter(
            PendingSignup.id == pending.id,
            PendingSignup.attempts_remaining > 0,
        ).update(
            {PendingSignup.attempts_remaining: PendingSignup.attempts_remaining - 1},
            synchronize_session=False,
        )
        db.session.commit()
        return uniform

    # Snapshot while the ORM object is guaranteed live (before any rollback).
    pending_username = pending.username

    # ── Race guard: the username/email may have been claimed since ───────
    if db.session.query(User).filter_by(username=pending_username).first():
        return jsonify({"error": "Username already taken."}), 409
    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    user = User(
        username=pending_username,
        email=email,
        password_hash=pending.password_hash,
        display_name=pending.display_name,
    )
    db.session.add(user)
    db.session.delete(pending)
    # Consume the invite code in the same commit that creates the account:
    # from this moment the code can never mint another account, and a failed
    # commit leaves it unconsumed (the person can simply retry).
    wl_entry = db.session.query(Waitlist).filter_by(email=email).first()
    if wl_entry is not None and wl_entry.status == "approved":
        wl_entry.status = "registered"
        wl_entry.code_used_at = _utcnow()
    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent verify/signup claimed the username or email between
        # the SELECT race guards and this commit. Map back to the same
        # 409s; fall back to the uniform body for anything else.
        db.session.rollback()
        if db.session.query(User).filter_by(username=pending_username).first():
            return jsonify({"error": "Username already taken."}), 409
        if db.session.query(User).filter_by(email=email).first():
            return jsonify({"error": "Email already registered."}), 409
        return uniform

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/resend", methods=["POST"])
def resend():
    """Re-issue a verification code. Constant response regardless of
    whether the email has a pending signup (anti-enumeration); cooldown
    and the resend cap are silent no-ops."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    ok = jsonify({"ok": True}), 200

    pending = db.session.query(PendingSignup).filter_by(email=email).first()
    now = _utcnow()
    if (
        not pending
        or now - pending.last_sent_at < RESEND_COOLDOWN
        or pending.resend_count >= MAX_RESENDS
    ):
        # Anti-timing-oracle: every silent no-op costs one bcrypt hash like
        # a real resend; only the outbound email's latency stays distinct.
        bcrypt.generate_password_hash("000000")
        return ok

    code = _generate_code()
    pending.code_hash = bcrypt.generate_password_hash(code).decode("utf-8")
    pending.code_expires_at = now + CODE_TTL
    pending.attempts_remaining = 5
    pending.resend_count += 1
    pending.last_sent_at = now

    try:
        get_email_provider().send_verification_code(email, code)
    except EmailSendError:
        db.session.rollback()
        return ok  # constant response even on send failure

    db.session.commit()
    return ok


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = db.session.query(User).filter_by(email=email).first()
    # Anti-timing-oracle: unknown emails cost the same bcrypt check as a
    # wrong password, so timing doesn't reveal which emails are registered.
    password_ok = bcrypt.check_password_hash(
        user.password_hash if user else _DUMMY_CODE_HASH, password
    )
    if not user or not password_ok:
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

    data = request.get_json(silent=True) or {}
    if "username" in data:
        uname = data["username"]
        if not isinstance(uname, str):
            return jsonify({"error": "Username must be a string."}), 400
        uname = uname.strip()
        if len(uname) > 80:
            return jsonify({"error": "Username must be at most 80 characters."}), 400
        if uname:
            existing = db.session.query(User).filter_by(username=uname).first()
            if existing and existing.id != user.id:
                return jsonify({"error": "Username already taken."}), 409
            user.username = uname
    if "bio" in data:
        if data["bio"] is not None and not isinstance(data["bio"], str):
            return jsonify({"error": "Bio must be a string."}), 400
        user.bio = (data["bio"] or "")[:500]
    if "avatar_url" in data:
        if data["avatar_url"] is not None and not isinstance(data["avatar_url"], str):
            return jsonify({"error": "Avatar URL must be a string."}), 400
        user.avatar_url = (data["avatar_url"] or "")[:300] or None
    if "display_name" in data:
        dn = data["display_name"]
        user.display_name = dn.strip()[:80] if isinstance(dn, str) and dn.strip() else None

    db.session.commit()
    return jsonify({"user": user.to_dict(include_stats=True)}), 200
