"""Unit + integration tests for routes.rec_signals.

The signal helpers are pure functions; profile builder + score_candidates
hit the DB and use the standard conftest fixtures.
"""

def test_module_has_schema_version():
    from routes import rec_signals
    assert isinstance(rec_signals.SIGNAL_PROFILE_SCHEMA_VERSION, int)
    assert rec_signals.SIGNAL_PROFILE_SCHEMA_VERSION >= 1


class TestStudioAffinity:
    def test_returns_zero_when_studio_unknown_to_user(self):
        from routes.rec_signals import _studio_affinity
        result = _studio_affinity("Studio X", [])
        assert result == 0.0

    def test_returns_hit_rate_for_known_studio(self):
        from routes.rec_signals import _studio_affinity
        top_studios = [{"name": "MAPPA", "hit_rate": 0.83, "n": 6}]
        result = _studio_affinity("MAPPA", top_studios)
        assert result == 0.83

    def test_studio_match_is_case_insensitive(self):
        from routes.rec_signals import _studio_affinity
        top_studios = [{"name": "MAPPA", "hit_rate": 0.83, "n": 6}]
        result = _studio_affinity("mappa", top_studios)
        assert result == 0.83

    def test_returns_zero_for_empty_candidate_studio(self):
        from routes.rec_signals import _studio_affinity
        top_studios = [{"name": "MAPPA", "hit_rate": 0.83, "n": 6}]
        assert _studio_affinity("", top_studios) == 0.0
        assert _studio_affinity(None, top_studios) == 0.0
