"""Tests for seed.py's destructive-drop guard.

seed() calls db.drop_all(). build.sh runs seed.py on deploy, so an
unguarded seed against a real (Postgres) DATABASE_URL would wipe
production. The guard only permits dropping a local SQLite file unless
explicitly forced.
"""
from seed import _drop_allowed


def test_local_sqlite_is_allowed():
    assert _drop_allowed("sqlite:///bingery.db", force=False) is True
    assert _drop_allowed("sqlite:///:memory:", force=False) is True


def test_postgres_blocked_without_force():
    assert _drop_allowed("postgresql://user:pw@host/db", force=False) is False
    assert _drop_allowed("postgres://user:pw@host/db", force=False) is False


def test_force_overrides_for_any_backend():
    assert _drop_allowed("postgresql://user:pw@host/db", force=True) is True
