"""Collections routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Collection


collections_bp = Blueprint("collections", __name__)


@collections_bp.route("", methods=["GET"])
@jwt_required()
def list_collections():
    user_id = int(get_jwt_identity())
    rows = Collection.query.filter_by(user_id=user_id).order_by(Collection.updated_at.desc()).all()
    return jsonify({"collections": [c.to_dict() for c in rows]})


@collections_bp.route("", methods=["POST"])
@jwt_required()
def create_collection():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "`name` is required"}), 400
    if len(name) > 80:
        return jsonify({"error": "`name` must be 80 characters or fewer"}), 400

    c = Collection(
        user_id=user_id,
        name=name,
        description=(data.get("description") or "")[:500] or None,
        color=(data.get("color") or "amber")[:16],
        icon=(data.get("icon") or "bookmark")[:32],
    )
    db.session.add(c)
    db.session.commit()
    return jsonify({"collection": c.to_dict()}), 201


def _owned_or_404(user_id: int, collection_id: int) -> Collection:
    c = Collection.query.filter_by(id=collection_id, user_id=user_id).first()
    if not c:
        from flask import abort
        abort(404)
    return c


@collections_bp.route("/<int:collection_id>", methods=["GET"])
@jwt_required()
def get_collection(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    return jsonify({"collection": c.to_dict(include_items=True)})


@collections_bp.route("/<int:collection_id>", methods=["PATCH"])
@jwt_required()
def update_collection(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name or len(name) > 80:
            return jsonify({"error": "invalid `name`"}), 400
        c.name = name
    if "description" in data:
        c.description = (data["description"] or "")[:500] or None
    if "color" in data:
        c.color = (data["color"] or "amber")[:16]
    if "icon" in data:
        c.icon = (data["icon"] or "bookmark")[:32]

    db.session.commit()
    return jsonify({"collection": c.to_dict()})


@collections_bp.route("/<int:collection_id>", methods=["DELETE"])
@jwt_required()
def delete_collection(collection_id: int):
    user_id = int(get_jwt_identity())
    c = _owned_or_404(user_id, collection_id)
    db.session.delete(c)
    db.session.commit()
    return "", 204
