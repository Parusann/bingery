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
