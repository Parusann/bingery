"""Tests for production boot guards in config.py."""
import importlib

import pytest


def test_fly_runtime_counts_as_production(monkeypatch):
    """If FLASK_ENV ever gets dropped from fly.toml, FLY_APP_NAME (always
    present on Fly machines) must still trigger the production boot guards
    instead of silently booting with dev defaults."""
    import config as config_module

    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLY_APP_NAME", "bingery")
    try:
        with pytest.raises(SystemExit):
            importlib.reload(config_module)
    finally:
        monkeypatch.delenv("FLY_APP_NAME")
        importlib.reload(config_module)


def test_production_requires_database_url(monkeypatch):
    """Production must refuse to boot without DATABASE_URL — otherwise it
    silently falls back to an ephemeral on-disk SQLite that resets on every
    redeploy."""
    import config as config_module

    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("JWT_SECRET_KEY", "y" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://bingery.example")
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "key")
    monkeypatch.setenv("EMAIL_FROM", "a@b.c")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FLY_APP_NAME", raising=False)
    try:
        with pytest.raises(SystemExit):
            importlib.reload(config_module)
    finally:
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        for k in ("FLASK_ENV", "SECRET_KEY", "JWT_SECRET_KEY", "CORS_ORIGINS",
                  "EMAIL_PROVIDER", "BREVO_API_KEY", "EMAIL_FROM"):
            monkeypatch.delenv(k, raising=False)
        importlib.reload(config_module)


def test_production_refuses_signup_open(monkeypatch):
    """SIGNUP_OPEN bypasses the per-person invite gate — dev/test only.
    Production must refuse to boot with it set even when every required
    secret is present."""
    import config as config_module

    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("JWT_SECRET_KEY", "y" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://bingery.example")
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "key")
    monkeypatch.setenv("EMAIL_FROM", "a@b.c")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/bingery.db")
    monkeypatch.setenv("SIGNUP_OPEN", "1")
    try:
        with pytest.raises(SystemExit):
            importlib.reload(config_module)
    finally:
        for k in ("FLASK_ENV", "SECRET_KEY", "JWT_SECRET_KEY", "CORS_ORIGINS",
                  "EMAIL_PROVIDER", "BREVO_API_KEY", "EMAIL_FROM"):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        monkeypatch.setenv("SIGNUP_OPEN", "1")  # conftest default for other suites
        importlib.reload(config_module)


def test_explicit_development_env_skips_guards(monkeypatch):
    """FLASK_ENV=development must stay guard-free even on Fly-like envs."""
    import config as config_module

    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("FLY_APP_NAME", "bingery")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    try:
        importlib.reload(config_module)  # must not raise
    finally:
        monkeypatch.delenv("FLY_APP_NAME")
        monkeypatch.delenv("FLASK_ENV")
        importlib.reload(config_module)
