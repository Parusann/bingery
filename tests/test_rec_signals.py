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


class TestGenreMatch:
    def test_zero_when_no_overlap(self):
        from routes.rec_signals import _genre_match
        candidate_genres = ["Sports"]
        user_top_genres = [["Drama", 4.2], ["Slice of Life", 3.1]]
        assert _genre_match(candidate_genres, user_top_genres) == 0.0

    def test_full_overlap_returns_one(self):
        from routes.rec_signals import _genre_match
        candidate_genres = ["Drama", "Slice of Life"]
        user_top_genres = [["Drama", 4.2], ["Slice of Life", 3.1]]
        assert _genre_match(candidate_genres, user_top_genres) == 1.0

    def test_partial_overlap_returns_weighted_share(self):
        from routes.rec_signals import _genre_match
        candidate_genres = ["Drama"]
        user_top_genres = [["Drama", 4.0], ["Slice of Life", 1.0]]
        # 4.0 of total 5.0 in user weight matches => 0.8
        assert abs(_genre_match(candidate_genres, user_top_genres) - 0.8) < 1e-6

    def test_empty_inputs_zero(self):
        from routes.rec_signals import _genre_match
        assert _genre_match([], []) == 0.0
        assert _genre_match(["Drama"], []) == 0.0
        assert _genre_match([], [["Drama", 1.0]]) == 0.0


class TestFanGenreMatch:
    def test_partial_match_returns_weighted_share(self):
        from routes.rec_signals import _fan_genre_match
        cand = ["melancholy", "talky"]
        user_fan = [["melancholy", 4], ["talky", 3], ["weird", 1]]
        # 7 of total 8 user weight matches => 0.875
        assert abs(_fan_genre_match(cand, user_fan) - 7/8) < 1e-6

    def test_empty_returns_zero(self):
        from routes.rec_signals import _fan_genre_match
        assert _fan_genre_match([], [["x", 1]]) == 0.0
        assert _fan_genre_match(["x"], []) == 0.0


class TestEraFit:
    def test_exact_year_match_returns_one(self):
        from routes.rec_signals import _era_fit
        assert _era_fit(2018, 2018) == 1.0

    def test_decreases_with_distance(self):
        from routes.rec_signals import _era_fit
        near = _era_fit(2020, 2018)
        far = _era_fit(2000, 2018)
        assert 0 < far < near < 1

    def test_none_inputs_return_zero(self):
        from routes.rec_signals import _era_fit
        assert _era_fit(None, 2018) == 0.0
        assert _era_fit(2018, None) == 0.0

    def test_six_year_gap_is_near_e_to_the_negative_half(self):
        from routes.rec_signals import _era_fit
        import math
        # sigma=6, so |delta|=6 yields exp(-0.5) ~ 0.6065
        assert abs(_era_fit(2018, 2024) - math.exp(-0.5)) < 1e-3


class TestEpisodeFit:
    def test_returns_short_share_for_short_anime(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(12, prefs) == 0.7

    def test_returns_medium_share_for_medium_anime(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(24, prefs) == 0.2

    def test_returns_long_share_for_long_anime(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(60, prefs) == 0.1

    def test_unknown_episode_count_returns_zero(self):
        from routes.rec_signals import _episode_fit
        prefs = {"short": 0.7, "medium": 0.2, "long": 0.1}
        assert _episode_fit(None, prefs) == 0.0
        assert _episode_fit(0, prefs) == 0.0


class TestSurpriseBonus:
    def test_full_bonus_for_obscure_high_quality(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1, 2, 3}
        # api_score >= 8 AND not in top_100
        assert _surprise_bonus(8.6, 999, top_100) == 1.0

    def test_half_bonus_for_quality_alone(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1, 999}
        # api_score >= 8 but IS in top_100
        assert _surprise_bonus(8.6, 999, top_100) == 0.5

    def test_half_bonus_for_obscurity_alone(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1}
        # not in top_100 but api_score < 8
        assert _surprise_bonus(7.0, 999, top_100) == 0.5

    def test_no_bonus_for_neither(self):
        from routes.rec_signals import _surprise_bonus
        top_100 = {1, 999}
        assert _surprise_bonus(7.0, 999, top_100) == 0.0

    def test_handles_none_api_score(self):
        from routes.rec_signals import _surprise_bonus
        # api_score=None counts as low quality; obscurity alone gives 0.5
        assert _surprise_bonus(None, 999, {1}) == 0.5


class TestWatchlistCoherence:
    def test_one_when_in_planning(self):
        from routes.rec_signals import _watchlist_coherence
        assert _watchlist_coherence(42, [1, 42, 100]) == 1

    def test_zero_when_not_in_planning(self):
        from routes.rec_signals import _watchlist_coherence
        assert _watchlist_coherence(42, [1, 100]) == 0
        assert _watchlist_coherence(42, []) == 0
