"""Dub-source tier health ("doctor") check.

Answers one question loudly: which dub-date tiers are actually delivering
real dates, and which are dark or erroring? A missing AnimeSchedule key used
to be swallowed as a generic fetch error while the synthetic seeder quietly
filled the gap — the schedule then showed ~100% estimated dub dates with no
operational signal. This module turns that state into an explicit report,
used by:

* `GET /api/admin/dub-doctor` (ops visibility),
* `POST /api/admin/sync-dub-sources` (attached to every sync result),
* `sync_dub_animeschedule.py` (loud CLI failure when the key is absent),
* the schedule auditor's tier-health section (live probe during audits).

States: "live" (wrote real rows recently), "configured" (credentials look
fine but no recent writes — worth watching), "dark" (missing credentials,
tier cannot work), "idle" (nothing expected from it right now).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from utils.dub_sources.animeschedule import ANIMESCHEDULE_API_KEY_ENV

# A real tier that hasn't written anything in this long is suspicious even
# with credentials present (feed moved, key expired upstream, matcher broken).
STALE_WRITE_DAYS = 14

# Fraction of upcoming dub dates that are synthetic estimates above which the
# dub pipeline should be considered dark end-to-end (matches the audit
# threshold documented in docs/runbooks/schedule-audit.md).
SYNTHETIC_ALARM_FRACTION = 0.6


def _tier_write_stats(session, source: str) -> dict:
    from sqlalchemy import func
    from models import Episode

    count, latest = (
        session.query(func.count(Episode.id), func.max(Episode.updated_at))
        .filter(Episode.dub_source == source)
        .one()
    )
    return {"rows": count or 0, "latest_write": latest.isoformat() if latest else None}


def dub_tier_health(session=None) -> dict:
    """Build the tier-health report. Requires an app context (DB reads only)."""
    from models import db, Episode
    from sqlalchemy import func
    from seed_dub_schedule import SYNTHETIC_TAG

    session = session or db.session
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stale_cutoff = now - timedelta(days=STALE_WRITE_DAYS)

    tiers = []

    def _classify_real_tier(name: str, *, dark: bool, dark_detail: str = ""):
        stats = _tier_write_stats(session, name)
        if dark:
            state, detail = "dark", dark_detail
        elif stats["latest_write"] and datetime.fromisoformat(
            stats["latest_write"]
        ) >= stale_cutoff:
            state, detail = "live", ""
        elif stats["rows"]:
            state = "configured"
            detail = f"no writes in {STALE_WRITE_DAYS}d — key expired or feed moved?"
        else:
            state, detail = "configured", "credentials look fine; never written"
        tiers.append({"tier": name, "state": state, "detail": detail, **stats})

    # Tier 1 — Crunchyroll RSS (keyless; only write-evidence can vouch for it)
    _classify_real_tier("crunchyroll_rss", dark=False)

    # Tier 2 — AnimeSchedule.net (Bearer key required)
    key_missing = not os.environ.get(ANIMESCHEDULE_API_KEY_ENV)
    _classify_real_tier(
        "animeschedule",
        dark=key_missing,
        dark_detail=(
            f"{ANIMESCHEDULE_API_KEY_ENV} is not set — the live endpoint 401s, "
            "no real dub dates can sync, synthetic estimates fill the schedule. "
            "Provision a token at https://animeschedule.net/ (account settings)."
        ),
    )

    # Tier 3 — research ingest + user reports (attended tiers; idle is normal)
    for name, matcher in (("research", Episode.dub_source == "research"),
                          ("user_reports", Episode.dub_source.like("user:%"))):
        count, latest = (
            session.query(func.count(Episode.id), func.max(Episode.updated_at))
            .filter(matcher)
            .one()
        )
        tiers.append({
            "tier": name,
            "state": "live" if count else "idle",
            "detail": "",
            "rows": count or 0,
            "latest_write": latest.isoformat() if latest else None,
        })

    # Synthetic pressure: how much of the next 14 days of dub schedule is a
    # projection rather than a real date? High fraction = real tiers dark.
    horizon = now + timedelta(days=14)
    upcoming = (
        session.query(
            func.count(Episode.id),
            func.sum(
                (Episode.dub_source == SYNTHETIC_TAG).cast(db.Integer)
            ),
        )
        .filter(Episode.air_date_dub >= now, Episode.air_date_dub < horizon)
        .one()
    )
    total, synthetic = upcoming[0] or 0, upcoming[1] or 0
    fraction = round(synthetic / total, 4) if total else 0.0

    alarms = [
        f"{t['tier']}: {t['detail']}" for t in tiers if t["state"] == "dark"
    ]
    if total and fraction > SYNTHETIC_ALARM_FRACTION:
        alarms.append(
            f"synthetic fraction of next-14d dub dates is {fraction:.0%} "
            f"(> {SYNTHETIC_ALARM_FRACTION:.0%}) — real dub tiers are not delivering"
        )

    return {
        "tiers": tiers,
        "upcoming_14d": {
            "dub_entries": total,
            "synthetic": synthetic,
            "synthetic_fraction": fraction,
        },
        "alarms": alarms,
        "healthy": not alarms,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
