from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from models import db, User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
bcrypt = Bcrypt()


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

    # ── Create user ───────────────────────────────────────────────────────
    user = User(
        username=username,
        email=email,
        password_hash=bcrypt.generate_password_hash(data["password"]).decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


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

    db.session.commit()
    return jsonify({"user": user.to_dict(include_stats=True)}), 200
