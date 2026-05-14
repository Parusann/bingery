"""Dub-report endpoints — Tier 3 of Plan 4 Phase B (user-submitted dub dates).

Endpoints:
    POST   /api/dub-reports                — any authenticated user submits a report
    GET    /api/dub-reports?status=pending — admin reads the moderation queue
    PATCH  /api/dub-reports/<id>           — admin accepts/rejects a report

Admin model: "first-user-as-admin" (user.id == 1). This is the pragmatic
default chosen in the Plan 4 spec; a proper `is_admin` flag can replace it
later without endpoint changes.

When a report is accepted, the linked Episode's `air_date_dub` is overwritten
unconditionally (Tier 3 has the highest precedence — a human says it's right)
and `dub_source` is set to `user:<submitter_username>`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from models import DubReport, Episode, User, db


dub_reports_bp = Blueprint("dub_reports", __name__)

ADMIN_USER_ID = 1
VALID_TARGET_STATUSES = {"accepted", "rejected"}


# ─── Helpers ────────────────────────────────────────────────────────────────


def _current_user() -> User | None:
    raw_id = get_jwt_identity()
    if raw_id is None:
        return None
    try:
        user_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id)


def _is_admin(user: User | None) -> bool:
    return user is not None and user.id == ADMIN_USER_ID


def _parse_iso(s: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime (accepts trailing Z). Returns UTC-aware or None."""
    if not isinstance(s, str) or not s.strip():
        return None
    raw = s.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ─── POST /api/dub-reports ──────────────────────────────────────────────────


@dub_reports_bp.route("", methods=["POST"])
@jwt_required()
def create_dub_report():
    user = _current_user()
    if user is None:
        return jsonify({"error": "user not found"}), 401

    body = request.get_json(silent=True) or {}
    episode_id = body.get("episode_id")
    air_date_raw = body.get("air_date")
    note = body.get("note")

    if not isinstance(episode_id, int):
        return jsonify({"error": "episode_id must be an integer"}), 400

    episode = db.session.get(Episode, episode_id)
    if episode is None:
        return jsonify({"error": "episode not found"}), 400

    air_date = _parse_iso(air_date_raw)
    if air_date is None:
        return (
            jsonify({"error": "air_date must be ISO-8601 (YYYY-MM-DDTHH:MM:SSZ)"}),
            400,
        )

    if note is not None and not isinstance(note, str):
        return jsonify({"error": "note must be a string when present"}), 400
    if isinstance(note, str) and len(note) > 500:
        return jsonify({"error": "note must be 500 chars or fewer"}), 400

    existing = (
        DubReport.query
        .filter_by(submitted_by=user.id, episode_id=episode.id)
        .first()
    )
    if existing is not None:
        return (
            jsonify(
                {
                    "error": "you have already submitted a report for this episode",
                    "report": existing.to_dict(),
                }
            ),
            409,
        )

    report = DubReport(
        episode_id=episode.id,
        submitted_by=user.id,
        air_date=air_date,
        note=note if isinstance(note, str) else None,
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({"report": report.to_dict()}), 201


# ─── GET /api/dub-reports ───────────────────────────────────────────────────


@dub_reports_bp.route("", methods=["GET"])
@jwt_required()
def list_dub_reports():
    user = _current_user()
    if not _is_admin(user):
        return jsonify({"error": "admin only"}), 403

    status_filter = request.args.get("status")
    q = DubReport.query
    if status_filter:
        q = q.filter(DubReport.status == status_filter)
    q = q.order_by(DubReport.created_at.desc())
    return jsonify({"reports": [r.to_dict() for r in q.all()]}), 200


# ─── PATCH /api/dub-reports/<id> ────────────────────────────────────────────


@dub_reports_bp.route("/<int:report_id>", methods=["PATCH"])
@jwt_required()
def update_dub_report(report_id: int):
    user = _current_user()
    if not _is_admin(user):
        return jsonify({"error": "admin only"}), 403

    report = db.session.get(DubReport, report_id)
    if report is None:
        return jsonify({"error": "report not found"}), 404

    body = request.get_json(silent=True) or {}
    target_status = body.get("status")
    if target_status not in VALID_TARGET_STATUSES:
        return (
            jsonify({"error": "status must be 'accepted' or 'rejected'"}),
            400,
        )

    if target_status == "accepted":
        episode = db.session.get(Episode, report.episode_id)
        if episode is None:
            # Cascade rules normally prevent this, but guard for safety.
            return jsonify({"error": "linked episode no longer exists"}), 409
        submitter = db.session.get(User, report.submitted_by)
        username = submitter.username if submitter else f"id{report.submitted_by}"
        episode.air_date_dub = report.air_date
        episode.dub_source = f"user:{username}"

    report.status = target_status
    report.reviewed_at = datetime.now(timezone.utc)
    report.reviewed_by = user.id
    db.session.commit()
    return jsonify({"report": report.to_dict()}), 200
