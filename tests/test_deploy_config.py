"""Guards on the deploy config so retired infrastructure and the standing
schedule-maintenance jobs can't silently regress."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_build_sh_does_not_seed():
    """build.sh must not invoke seed.py (which drops all tables). Comments
    mentioning it are fine."""
    code_lines = [
        ln for ln in _read("build.sh").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert not any("seed.py" in ln for ln in code_lines)


def test_render_config_stays_retired():
    """render.yaml was removed 2026-07-10: the Render stack (own Postgres +
    crons) maintained a database the Fly app never read — the split-brain
    that let statuses go stale. Re-adding it would recreate that trap; new
    scheduled jobs belong in .github/workflows/refresh-schedule.yml calling
    the in-process admin endpoints on Fly."""
    assert not os.path.exists(os.path.join(ROOT, "render.yaml"))


def test_daily_workflow_keeps_the_standing_schedule_jobs():
    """The daily workflow is now the only automation keeping the schedule
    honest. It must keep (1) the anti-drift AniList window refresh — without
    it, finished shows drift stale and ghosts rebuild — and (2) the
    post-sync audit that alarms when accuracy degrades."""
    content = _read(os.path.join(".github", "workflows", "refresh-schedule.yml"))
    assert '"mode": "window"' in content
    assert "/api/anilist/sync" in content
    assert "/api/admin/audit-schedule" in content
    assert "/api/admin/sync-dub-sources" in content
