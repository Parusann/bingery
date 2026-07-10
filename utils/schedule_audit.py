"""Schedule audit core — classification logic for the weekly-schedule auditor.

This module is pure logic (no network, no Flask): given the entries the
schedule serves and the claims independent sources make about them, it
classifies every entry and assembles a machine-readable report.

Classes of result per entry (one entry = one episode on one track):

* CONFIRMED     — at least two independent voices agree with our date
                  (same UTC calendar day; ±1 day tolerated when either side
                  is a date-only listing, absorbing the JST-broadcast vs
                  simulcast-listing offset).
* MISMATCH      — at least two independent voices agree with each other on a
                  *different* date (or the confirmed status contradicts the
                  row's existence); the consensus value and every source's
                  answer are recorded.
* ESTIMATED     — the row is the synthetic projection (`dub_source ==
                  SYNTHETIC_TAG`). Legitimate only because the UI labels it;
                  the serving layer derives its `estimated` flag from the
                  same `dub_source` value, so labeling is structural.
* UNVERIFIABLE  — fewer than two voices had anything to say. Flagged, never
                  guessed.

Source independence: MyAnimeList and Jikan expose the same underlying MAL
data, so they count as ONE voice ("myanimelist") no matter which transport
answered. AniList, AnimeSchedule, Crunchyroll and attended web research are
each their own voice.

Per-track status rules: a finished sub with an ongoing dub is legitimate
schedule content for the dub track — dub entries are only leak-flagged on
*dub-track* evidence (or when the episode number exceeds the confirmed
total episode count, in which case the episode cannot exist on any track).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from seed_dub_schedule import SYNTHETIC_TAG

JST = ZoneInfo("Asia/Tokyo")

# Classification labels
CONFIRMED = "CONFIRMED"
MISMATCH = "MISMATCH"
ESTIMATED = "ESTIMATED"
UNVERIFIABLE = "UNVERIFIABLE"

# Canonical per-track statuses
ST_AIRING = "airing"
ST_FINISHED = "finished"
ST_UPCOMING = "upcoming"
ST_CANCELLED = "cancelled"
ST_HIATUS = "hiatus"
ST_UNKNOWN = "unknown"

_DB_STATUS_MAP = {
    "currently airing": ST_AIRING,
    "airing": ST_AIRING,
    "finished airing": ST_FINISHED,
    "completed": ST_FINISHED,
    "upcoming": ST_UPCOMING,
    "not yet aired": ST_UPCOMING,
    "cancelled": ST_CANCELLED,
    "hiatus": ST_HIATUS,
}


def canonical_db_status(raw: Optional[str]) -> str:
    return _DB_STATUS_MAP.get((raw or "").strip().lower(), ST_UNKNOWN)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def dates_agree(
    a: datetime,
    b: datetime,
    *,
    a_date_only: bool = False,
    b_date_only: bool = False,
) -> bool:
    """Same UTC calendar day; ±1 day when either side is date-only.

    A date-only claim (e.g. a timetable that lists "July 12" with no time)
    can land on the adjacent UTC day of a JST broadcast timestamp — the
    classic JST-midnight vs UTC-afternoon offset — so it gets one day of
    slack. Two full timestamps must agree on the exact UTC day.
    """
    day_a = _utc(a).date()
    day_b = _utc(b).date()
    diff = abs((day_a - day_b).days)
    if diff == 0:
        return True
    return diff <= 1 and (a_date_only or b_date_only)


@dataclass
class SourceClaim:
    """One source's answer about one entry (or its anime).

    kind:
      episode_date — source lists this exact episode with a date/timestamp
      weekly_slot  — source publishes the show's weekly broadcast slot
                     (JST weekday); corroborates any date on that weekday
                     while the show is airing
      status       — source's per-track airing status for the anime
    """

    source: str                      # voice name, e.g. "anilist", "myanimelist"
    kind: str                        # "episode_date" | "weekly_slot" | "status"
    date: Optional[datetime] = None  # UTC-aware for episode_date
    date_only: bool = False
    status: Optional[str] = None     # canonical status for kind="status"
    track: str = "sub"               # which track the claim speaks about
    episode_number: Optional[int] = None
    jst_weekday: Optional[int] = None  # 0=Mon .. 6=Sun, for weekly_slot
    total_episodes: Optional[int] = None
    match_confidence: float = 100.0  # 100 = matched by provider ID
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "kind": self.kind,
            "date": self.date.isoformat() if self.date else None,
            "date_only": self.date_only,
            "status": self.status,
            "track": self.track,
            "episode_number": self.episode_number,
            "jst_weekday": self.jst_weekday,
            "total_episodes": self.total_episodes,
            "match_confidence": self.match_confidence,
            "detail": self.detail,
        }


@dataclass
class TierHealth:
    name: str
    state: str = "skipped"   # live | dark | error | skipped
    detail: str = ""
    requests: int = 0
    claims: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "detail": self.detail,
            "requests": self.requests,
            "claims": self.claims,
        }


@dataclass
class EntryAudit:
    anime_id: int
    anime_title: str
    anilist_id: Optional[int]
    mal_id: Optional[int]
    episode_id: int
    episode_number: int
    track: str                        # "sub" | "dub"
    our_date: datetime                # UTC-aware
    our_source: Optional[str]
    synthetic: bool
    db_status: str
    classification: str = UNVERIFIABLE
    supporting_voices: list = field(default_factory=list)
    consensus_date: Optional[datetime] = None   # for MISMATCH: what sources agree on
    match_confidence: float = 0.0
    leak: bool = False
    leak_reason: str = ""
    status_live: str = ST_UNKNOWN     # confirmed live status for this entry's track
    status_stale: bool = False        # DB status contradicts confirmed live status
    claims: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "anime_id": self.anime_id,
            "anime_title": self.anime_title,
            "anilist_id": self.anilist_id,
            "mal_id": self.mal_id,
            "episode_id": self.episode_id,
            "episode_number": self.episode_number,
            "track": self.track,
            "our_date": self.our_date.isoformat(),
            "our_source": self.our_source,
            "synthetic": self.synthetic,
            "db_status": self.db_status,
            "classification": self.classification,
            "supporting_voices": self.supporting_voices,
            "consensus_date": (
                self.consensus_date.isoformat() if self.consensus_date else None
            ),
            "match_confidence": self.match_confidence,
            "leak": self.leak,
            "leak_reason": self.leak_reason,
            "status_live": self.status_live,
            "status_stale": self.status_stale,
            "claims": [c.to_dict() for c in self.claims],
            "notes": self.notes,
        }


# ─── Per-anime status consensus ─────────────────────────────────────────────


def consensus_status(claims: Iterable[SourceClaim], track: str) -> tuple[str, list[str]]:
    """Return (status, voices) — the live status for one track.

    Two voices agreeing → that status. One voice only → returned as-is but
    the caller can see len(voices) == 1 and treat it as weaker evidence.
    """
    votes: dict[str, set[str]] = {}
    for c in claims:
        if c.kind != "status" or c.track != track or not c.status:
            continue
        votes.setdefault(c.status, set()).add(c.source)
    if not votes:
        return ST_UNKNOWN, []
    status, voices = max(votes.items(), key=lambda kv: len(kv[1]))
    return status, sorted(voices)


def episode_count_overrun(
    claims: Iterable[SourceClaim], episode_number: int
) -> tuple[Optional[int], bool]:
    """Return (confirmed_total, overrun_is_evidenced) for one episode number.

    The overrun verdict follows the same two-voice discipline as status:
    an episode "past the finale" is evidenced when at least two ID-matched
    voices report totals below it, or when one voice does AND no voice says
    the show is still airing (a lone total against a dissenting RELEASING
    claim is a cross-source disagreement — flag it, don't guess). The
    reported total is the max any voice claims (never contradict a source
    that says the episode exists).
    """
    claims = list(claims)
    totals = {
        c.source: c.total_episodes
        for c in claims
        if c.total_episodes and c.match_confidence >= 100.0
    }
    if not totals:
        return None, False
    confirmed = max(totals.values())
    below = [s for s, t in totals.items() if t < episode_number]
    airing_voices = {
        c.source
        for c in claims
        if c.kind == "status" and c.track == "sub" and c.status == ST_AIRING
    }
    evidenced = (
        episode_number > confirmed
        and (len(below) >= 2 or (len(below) == 1 and not airing_voices))
    )
    return confirmed, evidenced


# ─── Entry classification ───────────────────────────────────────────────────


def _weekly_slot_agrees(claim: SourceClaim, our_date: datetime) -> bool:
    if claim.jst_weekday is None:
        return False
    return _utc(our_date).astimezone(JST).weekday() == claim.jst_weekday


def classify_entry(
    entry: EntryAudit,
    claims: list[SourceClaim],
    *,
    now: Optional[datetime] = None,
) -> EntryAudit:
    """Classify one served entry against every claim about its anime.

    Populates classification, supporting voices, consensus date, leak flags
    and per-track live status on the entry (mutates and returns it).
    """
    now = now or datetime.now(timezone.utc)
    entry.claims = claims

    # Live status for THIS entry's track, and sub status for parent checks.
    entry.status_live, status_voices = consensus_status(claims, entry.track)
    sub_status, sub_voices = consensus_status(claims, "sub")

    # DB status only models the sub track, so staleness is judged against it
    # with two independent voices behind the live value.
    if (
        entry.track == "sub"
        and len(status_voices) >= 2
        and entry.status_live != ST_UNKNOWN
        and entry.db_status != entry.status_live
    ):
        entry.status_stale = True
    if (
        entry.track == "dub"
        and len(sub_voices) >= 2
        and sub_status != ST_UNKNOWN
        and entry.db_status != sub_status
    ):
        entry.status_stale = True
        entry.notes.append(
            f"db status '{entry.db_status}' vs live sub status '{sub_status}'"
        )

    # Gather date evidence for this specific episode on this track.
    exact = [
        c
        for c in claims
        if c.kind == "episode_date"
        and c.track == entry.track
        and c.episode_number == entry.episode_number
        and c.date is not None
    ]
    slots = [
        c
        for c in claims
        if c.kind == "weekly_slot" and c.track == entry.track
    ]

    # A row stored at exactly UTC midnight is almost always a date-only
    # ingest (research rows, manual fixes) — give it the same ±1 day grace
    # a date-only source claim gets.
    our_date_only = (
        entry.our_date.hour == 0
        and entry.our_date.minute == 0
        and entry.our_date.second == 0
    )

    supporting: dict[str, SourceClaim] = {}
    for c in exact:
        if dates_agree(
            entry.our_date,
            c.date,
            a_date_only=our_date_only,
            b_date_only=c.date_only,
        ):
            supporting.setdefault(c.source, c)
    # A weekly slot corroborates our date only while the source says the
    # track is still running (a slot for a finished show confirms nothing).
    if entry.status_live in (ST_AIRING, ST_UNKNOWN):
        for c in slots:
            if _weekly_slot_agrees(c, entry.our_date):
                supporting.setdefault(c.source, c)

    entry.supporting_voices = sorted(supporting)
    if supporting:
        entry.match_confidence = min(c.match_confidence for c in supporting.values())

    # Consensus among sources that disagree with us: group exact-date claims
    # by UTC day and look for a day at least two voices share (a weekly-slot
    # voice cannot vote for a specific different day).
    contradicting = [c for c in exact if c.source not in supporting]
    by_day: dict = {}
    for c in contradicting:
        by_day.setdefault(_utc(c.date).date(), set()).add(c.source)
    mismatch_day = None
    for day, voices in sorted(by_day.items()):
        if len(voices) >= 2:
            mismatch_day = day
            break

    total_eps, overrun = episode_count_overrun(claims, entry.episode_number)
    if (
        total_eps is not None
        and entry.episode_number > total_eps
        and not overrun
    ):
        # One voice's total says this episode can't exist while another
        # voice disagrees (or says the show is still airing) — a genuine
        # cross-source disagreement for attended research, not a verdict.
        entry.notes.append(
            f"sources disagree: episode {entry.episode_number} exceeds one "
            f"voice's total ({total_eps}) but another voice contests it"
        )

    # ── Classification ──
    if entry.synthetic:
        entry.classification = ESTIMATED
        if mismatch_day is not None:
            entry.notes.append(
                "real sources agree on a different date — correction candidate"
            )
            entry.consensus_date = datetime.combine(
                mismatch_day, datetime.min.time(), tzinfo=timezone.utc
            )
    elif len(supporting) >= 2:
        entry.classification = CONFIRMED
    elif mismatch_day is not None:
        entry.classification = MISMATCH
        entry.consensus_date = datetime.combine(
            mismatch_day, datetime.min.time(), tzinfo=timezone.utc
        )
    elif overrun:
        # No source can list this episode because it does not exist.
        entry.classification = MISMATCH
        entry.notes.append(
            f"episode {entry.episode_number} > confirmed total {total_eps}"
        )
    else:
        entry.classification = UNVERIFIABLE

    # ── Leak rules (per track, evidence-gated) ──
    future = _utc(entry.our_date) > now
    if overrun:
        entry.leak = True
        entry.leak_reason = (
            f"episode {entry.episode_number} exceeds confirmed episode count "
            f"{total_eps} — episode does not exist on any track"
        )
    elif entry.track == "sub":
        if (
            future
            and entry.status_live in (ST_FINISHED, ST_CANCELLED)
            and len(status_voices) >= 2
            and not supporting
        ):
            entry.leak = True
            entry.leak_reason = (
                f"sub track is {entry.status_live} per {status_voices} but a "
                "future-dated episode is being served"
            )
    else:  # dub — only dub-track evidence may flag a leak
        if (
            future
            and entry.status_live == ST_FINISHED
            and len(status_voices) >= 2
            and not supporting
        ):
            entry.leak = True
            entry.leak_reason = (
                f"dub track is finished per {status_voices} but a future-dated "
                "dub episode is being served"
            )

    return entry


# ─── Report assembly ────────────────────────────────────────────────────────


@dataclass
class AuditReport:
    window_start: datetime
    window_end: datetime
    generated_at: datetime
    entries: list = field(default_factory=list)          # list[EntryAudit]
    tiers: list = field(default_factory=list)            # list[TierHealth]
    notes: list = field(default_factory=list)

    def totals(self) -> dict:
        out = {}
        for track in ("sub", "dub"):
            rows = [e for e in self.entries if e.track == track]
            out[track] = {
                "entries": len(rows),
                "confirmed": sum(1 for e in rows if e.classification == CONFIRMED),
                "mismatch": sum(1 for e in rows if e.classification == MISMATCH),
                "estimated": sum(1 for e in rows if e.classification == ESTIMATED),
                "unverifiable": sum(
                    1 for e in rows if e.classification == UNVERIFIABLE
                ),
                "leaks": sum(1 for e in rows if e.leak),
                "stale_status": sum(1 for e in rows if e.status_stale),
            }
        dub_rows = [e for e in self.entries if e.track == "dub"]
        out["synthetic_dub_fraction"] = (
            round(sum(1 for e in dub_rows if e.synthetic) / len(dub_rows), 4)
            if dub_rows
            else 0.0
        )
        out["mismatch_total"] = out["sub"]["mismatch"] + out["dub"]["mismatch"]
        out["leak_total"] = out["sub"]["leaks"] + out["dub"]["leaks"]
        out["stale_status_anime"] = len(
            {e.anime_id for e in self.entries if e.status_stale}
        )
        return out

    def to_dict(self) -> dict:
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "totals": self.totals(),
            "tiers": [t.to_dict() for t in self.tiers],
            "mismatches": [
                e.to_dict()
                for e in self.entries
                if e.classification == MISMATCH
            ],
            "leaks": [e.to_dict() for e in self.entries if e.leak],
            "entries": [e.to_dict() for e in self.entries],
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary_markdown(self) -> str:
        t = self.totals()
        lines = [
            "# Schedule audit report",
            "",
            f"- Window: {self.window_start.date()} → {self.window_end.date()} (UTC)",
            f"- Generated: {self.generated_at.isoformat()}",
            "",
            "## Totals",
            "",
            "| track | entries | confirmed | mismatch | estimated | unverifiable | leaks | stale status |",
            "|-------|---------|-----------|----------|-----------|--------------|-------|--------------|",
        ]
        for track in ("sub", "dub"):
            r = t[track]
            lines.append(
                f"| {track} | {r['entries']} | {r['confirmed']} | {r['mismatch']} "
                f"| {r['estimated']} | {r['unverifiable']} | {r['leaks']} "
                f"| {r['stale_status']} |"
            )
        lines += [
            "",
            f"**Synthetic dub fraction: {t['synthetic_dub_fraction']:.0%}** "
            "(synthetic rows are UI-labeled estimates; a high fraction means "
            "the real dub tiers are dark)",
            f"Anime with stale DB status: {t['stale_status_anime']}",
            "",
            "## Source tiers",
            "",
            "| tier | state | requests | claims | detail |",
            "|------|-------|----------|--------|--------|",
        ]
        for tier in self.tiers:
            lines.append(
                f"| {tier.name} | {tier.state} | {tier.requests} "
                f"| {tier.claims} | {tier.detail} |"
            )
        mismatches = [e for e in self.entries if e.classification == MISMATCH]
        lines += ["", f"## Mismatches ({len(mismatches)})", ""]
        for e in mismatches:
            lines.append(
                f"- **{e.anime_title}** ep {e.episode_number} [{e.track}] — ours "
                f"{e.our_date.date()} (source={e.our_source}); "
                + (
                    f"consensus {e.consensus_date.date()}; "
                    if e.consensus_date
                    else ""
                )
                + "answers: "
                + "; ".join(
                    f"{c.source}={c.date.date() if c.date else c.status}"
                    f"(conf {c.match_confidence:.0f})"
                    for c in e.claims
                    if c.kind == "episode_date" or c.kind == "status"
                )
            )
        leaks = [e for e in self.entries if e.leak]
        lines += ["", f"## Leaks ({len(leaks)})", ""]
        for e in leaks:
            lines.append(
                f"- **{e.anime_title}** ep {e.episode_number} [{e.track}] "
                f"{e.our_date.date()} — {e.leak_reason}"
            )
        if self.notes:
            lines += ["", "## Notes", ""] + [f"- {n}" for n in self.notes]
        return "\n".join(lines) + "\n"


# ─── Threshold gate (used by the CLI and CI) ────────────────────────────────


def evaluate_thresholds(
    totals: dict,
    *,
    max_mismatch: int = 5,
    max_synthetic_fraction: float = 0.6,
    max_leaks: int = 0,
) -> list[str]:
    """Return a list of human-readable breaches (empty = healthy).

    Defaults (documented in docs/runbooks/schedule-audit.md):
      * more than 5 MISMATCH entries — sync pipeline is writing bad dates
      * synthetic dub fraction above 60% — real dub tiers are dark
      * any confirmed leak — finished/nonexistent content is being served
    """
    breaches = []
    if totals["mismatch_total"] > max_mismatch:
        breaches.append(
            f"MISMATCH count {totals['mismatch_total']} exceeds {max_mismatch}"
        )
    if totals["synthetic_dub_fraction"] > max_synthetic_fraction:
        breaches.append(
            f"synthetic dub fraction {totals['synthetic_dub_fraction']:.0%} "
            f"exceeds {max_synthetic_fraction:.0%} — real dub tiers look dark"
        )
    if totals["leak_total"] > max_leaks:
        breaches.append(
            f"leak count {totals['leak_total']} exceeds {max_leaks}"
        )
    return breaches
