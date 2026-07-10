"""Tests for the schedule auditor — classification, per-track status rules,
leak evidence-gating, thresholds, and the end-to-end run_audit orchestration.
"""

from datetime import datetime, timedelta, timezone

import pytest

from models import db, Anime, Episode
from seed_dub_schedule import SYNTHETIC_TAG
from utils.schedule_audit import (
    CONFIRMED,
    ESTIMATED,
    MISMATCH,
    UNVERIFIABLE,
    ST_AIRING,
    ST_FINISHED,
    EntryAudit,
    SourceClaim,
    TierHealth,
    canonical_db_status,
    classify_entry,
    consensus_status,
    dates_agree,
    evaluate_thresholds,
)
from audit_schedule import enumerate_entries, run_audit, sunday_of

UTC = timezone.utc
NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)


def _entry(track="sub", date=None, synthetic=False, episode_number=5,
           db_status="airing"):
    return EntryAudit(
        anime_id=1,
        anime_title="Test Show",
        anilist_id=100,
        mal_id=200,
        episode_id=10,
        episode_number=episode_number,
        track=track,
        our_date=date or datetime(2026, 7, 12, 15, 0, tzinfo=UTC),
        our_source="anilist" if track == "sub" else (
            SYNTHETIC_TAG if synthetic else "crunchyroll_rss"
        ),
        synthetic=synthetic,
        db_status=db_status,
    )


def _date_claim(source, day, track="sub", episode_number=5, date_only=False,
                confidence=100.0):
    return SourceClaim(
        source=source, kind="episode_date", track=track,
        episode_number=episode_number,
        date=datetime(2026, 7, day, 15, 0, tzinfo=UTC),
        date_only=date_only, match_confidence=confidence,
    )


def _status_claim(source, status, track="sub", total=None):
    return SourceClaim(source=source, kind="status", track=track,
                       status=status, total_episodes=total)


# ─── dates_agree ─────────────────────────────────────────────────────────────


def test_dates_agree_same_utc_day():
    a = datetime(2026, 7, 12, 1, 0, tzinfo=UTC)
    b = datetime(2026, 7, 12, 23, 0, tzinfo=UTC)
    assert dates_agree(a, b)


def test_dates_disagree_adjacent_days_when_both_timestamped():
    a = datetime(2026, 7, 12, 23, 0, tzinfo=UTC)
    b = datetime(2026, 7, 13, 1, 0, tzinfo=UTC)
    assert not dates_agree(a, b)


def test_dates_agree_adjacent_day_when_one_side_date_only():
    # JST-midnight broadcast lands on the prior UTC afternoon; a date-only
    # listing gets one day of slack.
    a = datetime(2026, 7, 12, 16, 0, tzinfo=UTC)
    b = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
    assert dates_agree(a, b, b_date_only=True)


def test_dates_never_agree_two_days_apart():
    a = datetime(2026, 7, 12, 0, 0, tzinfo=UTC)
    b = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)
    assert not dates_agree(a, b, a_date_only=True, b_date_only=True)


# ─── status consensus ────────────────────────────────────────────────────────


def test_consensus_status_prefers_two_voices():
    claims = [
        _status_claim("anilist", ST_FINISHED),
        _status_claim("myanimelist", ST_FINISHED),
        _status_claim("web_research", ST_AIRING),
    ]
    status, voices = consensus_status(claims, "sub")
    assert status == ST_FINISHED
    assert voices == ["anilist", "myanimelist"]


def test_canonical_db_status_mapping():
    assert canonical_db_status("Currently Airing") == "airing"
    assert canonical_db_status("Finished Airing") == "finished"
    assert canonical_db_status("Upcoming") == "upcoming"
    assert canonical_db_status("???") == "unknown"


# ─── classification ──────────────────────────────────────────────────────────


def test_two_agreeing_voices_confirm():
    e = _entry()
    claims = [
        _date_claim("anilist", 12),
        _status_claim("anilist", ST_AIRING),
        SourceClaim(source="myanimelist", kind="weekly_slot", track="sub",
                    jst_weekday=datetime(2026, 7, 12, 15, 0, tzinfo=UTC)
                    .astimezone(timezone(timedelta(hours=9))).weekday()),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.classification == CONFIRMED
    assert set(e.supporting_voices) == {"anilist", "myanimelist"}


def test_single_voice_is_unverifiable():
    e = _entry()
    classify_entry(e, [_date_claim("anilist", 12)], now=NOW)
    assert e.classification == UNVERIFIABLE


def test_same_voice_twice_counts_once():
    # MAL + Jikan both answer as "myanimelist"; two claims from one voice
    # must never fake two-source confirmation.
    e = _entry()
    claims = [
        _date_claim("myanimelist", 12),
        _date_claim("myanimelist", 12),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.classification == UNVERIFIABLE


def test_two_voices_agreeing_elsewhere_is_mismatch_with_provenance():
    e = _entry()  # ours = July 12
    claims = [
        _date_claim("anilist", 14),
        _date_claim("animeschedule", 14, confidence=91.0),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.classification == MISMATCH
    assert e.consensus_date.date() == datetime(2026, 7, 14).date()
    assert len(e.claims) == 2  # every source's answer is preserved


def test_synthetic_row_is_estimated_even_when_sources_disagree():
    e = _entry(track="dub", synthetic=True)
    claims = [
        _date_claim("animeschedule", 14, track="dub", confidence=88.0),
        _date_claim("crunchyroll_rss", 14, track="dub", confidence=85.0),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.classification == ESTIMATED
    assert e.consensus_date is not None  # correction candidate is recorded
    assert any("correction candidate" in n for n in e.notes)


def test_no_claims_is_unverifiable_not_guessed():
    e = _entry(track="dub", synthetic=False)
    classify_entry(e, [], now=NOW)
    assert e.classification == UNVERIFIABLE
    assert not e.leak


# ─── leak rules per track ────────────────────────────────────────────────────


def test_future_sub_of_finished_show_is_leak():
    e = _entry(date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))  # future vs NOW
    claims = [
        _status_claim("anilist", ST_FINISHED),
        _status_claim("myanimelist", ST_FINISHED),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.leak
    assert "finished" in e.leak_reason


def test_past_sub_of_finished_show_is_history_not_leak():
    e = _entry(date=datetime(2026, 7, 6, 15, 0, tzinfo=UTC))  # past vs NOW
    claims = [
        _status_claim("anilist", ST_FINISHED),
        _status_claim("myanimelist", ST_FINISHED),
    ]
    classify_entry(e, claims, now=NOW)
    assert not e.leak


def test_ongoing_dub_of_finished_sub_is_not_a_leak():
    # The sub finished, but dub-track evidence says the dub is running:
    # this is legitimate dub-track content and must survive.
    e = _entry(track="dub", date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    claims = [
        _status_claim("anilist", ST_FINISHED),          # sub finished
        _status_claim("myanimelist", ST_FINISHED),      # sub finished
        _status_claim("animeschedule", ST_AIRING, track="dub"),
        _date_claim("animeschedule", 14, track="dub", confidence=90.0),
    ]
    classify_entry(e, claims, now=NOW)
    assert not e.leak
    assert e.status_live == ST_AIRING  # dub track's own status


def test_dub_leak_requires_dub_track_evidence():
    # Sub-finished alone must NOT leak-flag a dub row (dub sources silent).
    e = _entry(track="dub", synthetic=True,
               date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    claims = [
        _status_claim("anilist", ST_FINISHED),
        _status_claim("myanimelist", ST_FINISHED),
    ]
    classify_entry(e, claims, now=NOW)
    assert not e.leak
    assert e.classification == ESTIMATED


def test_nonexistent_episode_is_leak_on_any_track():
    e = _entry(track="dub", synthetic=True, episode_number=26,
               date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    claims = [
        _status_claim("anilist", ST_FINISHED, total=24),
        _status_claim("myanimelist", ST_FINISHED, total=24),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.leak
    assert "exceeds confirmed episode count" in e.leak_reason


def test_single_voice_episode_total_contested_is_not_a_leak():
    # AniList says the show is still RELEASING (total unknown); only MAL
    # claims 39 episodes. A lone total against a dissenting airing claim is
    # a cross-source disagreement — flagged for research, never a leak.
    e = _entry(track="dub", synthetic=True, episode_number=47,
               date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    claims = [
        _status_claim("anilist", ST_AIRING),           # no total, still airing
        _status_claim("myanimelist", ST_FINISHED, total=39),
    ]
    classify_entry(e, claims, now=NOW)
    assert not e.leak
    assert e.classification == ESTIMATED
    assert any("sources disagree" in n for n in e.notes)


def test_lone_total_with_no_dissent_still_leaks():
    # One voice's total, no voice claiming the show airs → evidenced overrun.
    e = _entry(episode_number=26,
               date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    claims = [_status_claim("myanimelist", ST_FINISHED, total=24)]
    classify_entry(e, claims, now=NOW)
    assert e.leak
    assert e.classification == MISMATCH


def test_stale_db_status_detected():
    e = _entry(db_status="airing",
               date=datetime(2026, 7, 6, 15, 0, tzinfo=UTC))
    claims = [
        _status_claim("anilist", ST_FINISHED),
        _status_claim("myanimelist", ST_FINISHED),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.status_stale


def test_weekly_slot_does_not_corroborate_finished_show():
    e = _entry(date=datetime(2026, 7, 14, 15, 0, tzinfo=UTC))
    jst_weekday = (datetime(2026, 7, 14, 15, 0, tzinfo=UTC)
                   .astimezone(timezone(timedelta(hours=9))).weekday())
    claims = [
        _status_claim("anilist", ST_FINISHED),
        _status_claim("myanimelist", ST_FINISHED),
        SourceClaim(source="myanimelist", kind="weekly_slot", track="sub",
                    jst_weekday=jst_weekday),
    ]
    classify_entry(e, claims, now=NOW)
    assert e.classification != CONFIRMED  # slot of a finished show proves nothing


# ─── thresholds ──────────────────────────────────────────────────────────────


def _totals(mismatch=0, synth_frac=0.0, leaks=0):
    return {
        "mismatch_total": mismatch,
        "synthetic_dub_fraction": synth_frac,
        "leak_total": leaks,
    }


def test_thresholds_healthy():
    assert evaluate_thresholds(_totals()) == []


def test_thresholds_breach_each_axis():
    assert len(evaluate_thresholds(_totals(mismatch=6))) == 1
    assert len(evaluate_thresholds(_totals(synth_frac=0.61))) == 1
    assert len(evaluate_thresholds(_totals(leaks=1))) == 1
    assert len(evaluate_thresholds(_totals(6, 0.61, 1))) == 3


def test_threshold_defaults_documented_values():
    # 5 mismatches / 60% synthetic / 0 leaks are the documented defaults.
    assert evaluate_thresholds(_totals(mismatch=5)) == []
    assert evaluate_thresholds(_totals(synth_frac=0.6)) == []
    assert evaluate_thresholds(_totals(leaks=0)) == []


# ─── sunday anchor ───────────────────────────────────────────────────────────


def test_sunday_of_returns_utc_sunday_midnight():
    anchor = sunday_of(datetime(2026, 7, 10, 18, 30, tzinfo=UTC))
    assert anchor.weekday() == 6  # Sunday
    assert anchor <= datetime(2026, 7, 10, tzinfo=UTC)
    assert (datetime(2026, 7, 10, tzinfo=UTC) - anchor).days < 7
    assert anchor.hour == 0 and anchor.minute == 0


# ─── end-to-end orchestration on the in-memory app ──────────────────────────


@pytest.fixture
def seeded(app):
    week = datetime(2026, 7, 5, tzinfo=UTC)  # Sunday anchor used below
    airing = Anime(title="Airing Show", status="Currently Airing",
                   anilist_id=100, mal_id=200)
    finished = Anime(title="Ghost Show", status="Currently Airing",  # stale!
                     anilist_id=101, mal_id=201)
    db.session.add_all([airing, finished])
    db.session.flush()
    eps = [
        Episode(anime_id=airing.id, episode_number=3,
                air_date_sub=datetime(2026, 7, 8, 15, 0),
                sub_source="anilist"),
        Episode(anime_id=airing.id, episode_number=2,
                air_date_dub=datetime(2026, 7, 9, 15, 0),
                dub_source=SYNTHETIC_TAG),
        Episode(anime_id=finished.id, episode_number=13,
                air_date_sub=datetime(2026, 7, 11, 15, 0),
                sub_source="anilist"),
    ]
    db.session.add_all(eps)
    db.session.commit()
    return {"week": week, "airing": airing, "finished": finished}


def test_enumerate_entries_covers_both_tracks(seeded):
    entries, anime = enumerate_entries(seeded["week"], 1)
    assert {(e.track, e.episode_number) for e in entries} == {
        ("sub", 3), ("sub", 13), ("dub", 2),
    }
    assert len(anime) == 2


def test_run_audit_offline_marks_synthetic_estimated(seeded):
    report = run_audit(week_start=seeded["week"], weeks=1, sources=[],
                       now=datetime(2026, 7, 10, tzinfo=UTC))
    totals = report.totals()
    assert totals["dub"]["entries"] == 1
    assert totals["dub"]["estimated"] == 1
    assert totals["synthetic_dub_fraction"] == 1.0
    assert totals["sub"]["unverifiable"] == 2
    assert all(t.state == "skipped" for t in report.tiers)


class FakeSource:
    """Injectable source: returns canned claims for the seeded fixture."""

    def __init__(self, name, claims_by_anilist_id):
        self.name = name
        self._claims = claims_by_anilist_id

    def collect(self, anime_records, start_utc, end_utc):
        health = TierHealth(name=self.name, state="live")
        out = {}
        for rec in anime_records:
            for claim in self._claims.get(rec["anilist_id"], []):
                out.setdefault(rec["id"], []).append(claim)
                health.claims += 1
        health.requests = 1
        return out, health


def test_run_audit_with_fake_sources_confirms_and_leak_flags(seeded):
    now = datetime(2026, 7, 10, tzinfo=UTC)
    anilist = FakeSource("anilist", {
        100: [
            _status_claim("anilist", ST_AIRING),
            SourceClaim(source="anilist", kind="episode_date", track="sub",
                        episode_number=3,
                        date=datetime(2026, 7, 8, 15, 0, tzinfo=UTC)),
        ],
        101: [_status_claim("anilist", ST_FINISHED, total=12)],
    })
    mal = FakeSource("myanimelist", {
        100: [
            _status_claim("myanimelist", ST_AIRING),
            SourceClaim(source="myanimelist", kind="episode_date", track="sub",
                        episode_number=3,
                        date=datetime(2026, 7, 8, 15, 0, tzinfo=UTC)),
        ],
        101: [_status_claim("myanimelist", ST_FINISHED, total=12)],
    })
    report = run_audit(week_start=seeded["week"], weeks=1,
                       sources=[anilist, mal], now=now)
    by_key = {(e.track, e.episode_number): e for e in report.entries}

    confirmed = by_key[("sub", 3)]
    assert confirmed.classification == CONFIRMED

    # Ghost Show: DB says airing, both voices say finished with 12 episodes;
    # our row claims episode 13 on July 12 (future) → leak + stale status.
    ghost = by_key[("sub", 13)]
    assert ghost.leak
    assert ghost.status_stale

    totals = report.totals()
    assert totals["leak_total"] == 1
    assert totals["stale_status_anime"] == 1
    assert [t.state for t in report.tiers] == ["live", "live"]
