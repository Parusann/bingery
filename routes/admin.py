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

import os
from datetime import timedelta

from flask import Blueprint, abort, jsonify, request

admin_bp = Blueprint("admin", __name__)


def _check_secret() -> None:
    expected = os.environ.get("ADMIN_SYNC_SECRET")
    if not expected:
        abort(503, description="ADMIN_SYNC_SECRET not configured on the server")
    if request.headers.get("X-Admin-Secret") != expected:
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
            ANIMESCHEDULE_URL,
            fetch_payload,
            ingest_payload,
        )
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

    return jsonify(results), 200
