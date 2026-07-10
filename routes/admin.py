"""Admin operations endpoint.

Currently exposes a single POST endpoint that runs the dub-source syncs +
synthetic seed reproject in-process inside the running gunicorn worker.

Why in-process: spawning `python sync_*.py` over `fly ssh` forks a brand-
new Python interpreter that has to re-import Flask + SQLAlchemy + models
(~100MB). On Fly's 256MB shared-cpu-1x that gets OOM-killed. Running the
sync logic inside the worker reuses the already-loaded imports, keeping
the peak memory delta to just the working set (~25MB).

Auth: header `X-Admin-Secret` must match the `ADMIN_SYNC_SECRET` env var.
"""

from __future__ import annotations

import hmac
import os
from datetime import timedelta

from flask import Blueprint, abort, jsonify, request

admin_bp = Blueprint("admin", __name__)


def _check_secret() -> None:
    expected = os.environ.get("ADMIN_SYNC_SECRET")
    if not expected:
        abort(503, description="ADMIN_SYNC_SECRET not configured on the server")
    provided = request.headers.get("X-Admin-Secret") or ""
    if not hmac.compare_digest(provided, expected):
        abort(401)


@admin_bp.route("/sync-dub-sources", methods=["POST"])
def sync_dub_sources():
    """Run Crunchyroll RSS + AnimeSchedule.net + synthetic seed reproject.

    AniList catalog sync is deliberately omitted — it takes 5-15 min and
    has no rolling window worth refreshing daily. Run it manually if the
    catalog status fields look stale.
    """
    _check_secret()

    results: dict[str, object] = {}

    # Crunchyroll RSS ────────────────────────────────────────────────────
    try:
        from utils.dub_sources.crunchyroll import (
            CR_RSS_URL,
            fetch_feed,
            ingest_feed,
        )
        xml = fetch_feed(CR_RSS_URL)
        results["crunchyroll"] = ingest_feed(xml)
    except Exception as exc:  # noqa: BLE001
        results["crunchyroll"] = {"error": f"{type(exc).__name__}: {exc}"}

    # AnimeSchedule.net ──────────────────────────────────────────────────
    try:
        from utils.dub_sources.animeschedule import (
            ANIMESCHEDULE_API_KEY_ENV,
            ANIMESCHEDULE_URL,
            fetch_payload,
            ingest_payload,
        )
        if not os.environ.get(ANIMESCHEDULE_API_KEY_ENV):
            # Do not disguise a missing key as a fetch error: the tier is
            # DARK and the schedule will be synthetic-only until it's fixed.
            results["animeschedule"] = {
                "tier": "dark",
                "error": (
                    f"{ANIMESCHEDULE_API_KEY_ENV} is not set — skipping fetch; "
                    "real dub dates will NOT sync and synthetic estimates "
                    "fill the gap"
                ),
            }
        else:
            payload = fetch_payload(ANIMESCHEDULE_URL)
            results["animeschedule"] = ingest_payload(payload)
    except Exception as exc:  # noqa: BLE001
        results["animeschedule"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Synthetic dub seed reproject ───────────────────────────────────────
    try:
        from seed_dub_schedule import main as seed_main
        # seed's main() pushes its own app_context — nested contexts are fine.
        rc = seed_main(["--overwrite", "--top", "1500"])
        results["seed"] = {"exit_code": rc}
    except SystemExit as exc:
        results["seed"] = {"exit_code": exc.code}
    except Exception as exc:  # noqa: BLE001
        results["seed"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Post-sync snapshot for telemetry
    try:
        from models import db, Episode
        from sqlalchemy import func
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        results["snapshot"] = {
            "total_dub_eps": (
                db.session.query(func.count(Episode.id))
                .filter(Episode.air_date_dub.isnot(None))
                .scalar()
            ),
            "by_source": dict(
                db.session.query(
                    Episode.dub_source, func.count(Episode.id)
                )
                .filter(Episode.air_date_dub.isnot(None))
                .group_by(Episode.dub_source)
                .all()
            ),
            "next_7d": (
                db.session.query(func.count(Episode.id))
                .filter(
                    Episode.air_date_dub >= now,
                    Episode.air_date_dub < now + timedelta(days=7),
                )
                .scalar()
            ),
            "next_14d": (
                db.session.query(func.count(Episode.id))
                .filter(
                    Episode.air_date_dub >= now,
                    Episode.air_date_dub < now + timedelta(days=14),
                )
                .scalar()
            ),
        }
    except Exception as exc:  # noqa: BLE001
        results["snapshot"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Tier doctor — every sync response says which tiers are live/dark so a
    # dark tier shows up in the cron logs instead of hiding behind estimates.
    try:
        from utils.dub_doctor import dub_tier_health

        results["dub_doctor"] = dub_tier_health()
    except Exception as exc:  # noqa: BLE001
        results["dub_doctor"] = {"error": f"{type(exc).__name__}: {exc}"}

    return jsonify(results), 200


@admin_bp.route("/dub-doctor", methods=["GET"])
def dub_doctor():
    """Report dub-tier health: live / configured / dark / idle per tier,
    plus the synthetic fraction of the next 14 days of dub dates."""
    _check_secret()

    from utils.dub_doctor import dub_tier_health

    return jsonify(dub_tier_health()), 200


@admin_bp.route("/audit-schedule", methods=["POST"])
def audit_schedule_endpoint():
    """Run the schedule auditor in-process and return its report.

    Read-only: verifies the entries `/api/schedule/week` serves against
    independent sources (AniList, MAL/Jikan, AnimeSchedule, Crunchyroll RSS)
    and classifies them CONFIRMED / MISMATCH / ESTIMATED / UNVERIFIABLE.
    Never writes to the database — corrections stay attended-only.

    Body (all optional): {"weeks": 1, "max_anime": 60, "offline": false}
    `weeks` is clamped to 1..4 and `max_anime` to 10..200 to keep the
    in-request runtime bounded (source calls are rate-limited).
    """
    _check_secret()

    body = request.get_json(silent=True) or {}
    try:
        weeks = max(1, min(int(body.get("weeks", 1)), 4))
        max_anime = max(10, min(int(body.get("max_anime", 60)), 200))
    except (TypeError, ValueError):
        return jsonify({"error": "weeks and max_anime must be integers"}), 400
    offline = bool(body.get("offline", False))

    from datetime import datetime, timezone

    from audit_schedule import run_audit, sunday_of
    from utils.schedule_audit import evaluate_thresholds

    report = run_audit(
        week_start=sunday_of(datetime.now(timezone.utc)),
        weeks=weeks,
        max_anime=max_anime,
        sources=[] if offline else None,
    )
    payload = report.to_dict()
    payload["threshold_breaches"] = evaluate_thresholds(report.totals())

    # Best-effort server-side copy for later inspection; the response body
    # is the artifact the CI workflow uploads.
    try:
        out_dir = os.path.join("reports", "schedule-audit")
        os.makedirs(out_dir, exist_ok=True)
        tag = report.generated_at.strftime("%Y%m%dT%H%M%SZ")
        with open(os.path.join(out_dir, f"{tag}-audit.json"), "w",
                  encoding="utf-8") as fh:
            fh.write(report.to_json())
    except OSError:
        pass

    return jsonify(payload), 200


@admin_bp.route("/ingest-dub-dates", methods=["POST"])
def ingest_dub_dates():
    """Ingest real dub air dates from a JSON batch (the "research" fallback).

    Body: {"rows": [...], "dub_source"?: str, "overwrite"?: bool}
    Each row: {anilist_id?|title?, episode_number, air_date(ISO-8601)}.

    Default dub_source="research": these dates upgrade NULL/synthetic rows and
    are preserved by the synthetic seeder, but won't clobber crunchyroll_rss /
    animeschedule / user:* unless overwrite=true. Powers the monthly research
    task that fills dub dates AnimeSchedule.net still misses.
    """
    _check_secret()

    body = request.get_json(silent=True) or {}
    rows = body.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "body must include a 'rows' array"}), 400

    dub_source = (body.get("dub_source") or "research").strip() or "research"
    overwrite = bool(body.get("overwrite", False))

    from utils.dub_sources.manual_ingest import ingest_dub_rows

    summary = ingest_dub_rows(rows, dub_source=dub_source, overwrite=overwrite)
    return jsonify(summary), 200
