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


class TestDroppedTraitPenalty:
    def test_zero_when_no_overlap(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        assert _dropped_trait_penalty("Good Studio", ["Drama"], dropped) == 0.0

    def test_half_for_studio_alone(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        assert _dropped_trait_penalty("Bad Studio", ["Drama"], dropped) == 0.5

    def test_genre_share_contribution(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": [], "genres": ["Ecchi", "Sports"]}
        # Both candidate genres are in the dropped list => 1.0 share => 0.5 weight
        assert _dropped_trait_penalty("Studio X", ["Ecchi", "Sports"], dropped) == 0.5

    def test_combined_full_penalty(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        # studio matches (+0.5) and 1/1 candidate genre matches (+0.5) => 1.0
        assert _dropped_trait_penalty("Bad Studio", ["Ecchi"], dropped) == 1.0

    def test_no_candidate_genres_uses_studio_only(self):
        from routes.rec_signals import _dropped_trait_penalty
        dropped = {"studios": ["Bad Studio"], "genres": ["Ecchi"]}
        assert _dropped_trait_penalty("Bad Studio", [], dropped) == 0.5


class TestScoreCandidate:
    def test_returns_signals_breakdown_and_total(self):
        from routes.rec_signals import score_candidate
        candidate = {
            "id": 42, "title": "X", "studio": "MAPPA",
            "genres": ["Drama"], "fan_genres": ["melancholy"],
            "api_score": 8.6, "year": 2018, "episodes": 12,
        }
        profile = {
            "top_genres": [["Drama", 1.0]],
            "top_studios": [{"name": "MAPPA", "hit_rate": 1.0, "n": 5}],
            "fan_genre_clusters": [["melancholy", 1]],
            "era_lean_year": 2018,
            "episode_fit_pref": {"short": 1.0, "medium": 0, "long": 0},
            "dropped_traits": {"studios": [], "genres": []},
            "watchlist_planning_ids": [],
        }
        top_100 = set()  # candidate 42 not in top-100
        result = score_candidate(candidate, profile, top_100)
        assert result["id"] == 42
        assert result["signals"]["studio_affinity"] == 1.0
        assert result["signals"]["genre_match"] == 1.0
        assert result["signals"]["fan_genre_match"] == 1.0
        assert abs(result["signals"]["era_fit"] - 1.0) < 1e-6
        assert result["signals"]["episode_fit"] == 1.0
        assert result["signals"]["surprise_factor"] == 1.0
        assert result["signals"]["watchlist_aligned"] == 0
        assert result["signals"]["dropped_trait_penalty"] == 0.0
        # All signals max out: 25+20+15+10+10+10 = 90; no watchlist (0), no penalty (0)
        assert abs(result["signals"]["total_score"] - 90.0) < 1e-6

    def test_penalty_subtracts_from_total(self):
        from routes.rec_signals import score_candidate
        candidate = {
            "id": 1, "title": "Y", "studio": "Bad", "genres": ["Ecchi"],
            "fan_genres": [], "api_score": 6.0, "year": 2020, "episodes": 12,
        }
        profile = {
            "top_genres": [], "top_studios": [], "fan_genre_clusters": [],
            "era_lean_year": 2020,
            "episode_fit_pref": {"short": 0, "medium": 0, "long": 0},
            "dropped_traits": {"studios": ["Bad"], "genres": ["Ecchi"]},
            "watchlist_planning_ids": [],
        }
        result = score_candidate(candidate, profile, {1})
        # era_fit only (1.0 * 10 = 10), penalty (1.0 * 20 = -20) => -10 floored to 0
        assert result["signals"]["dropped_trait_penalty"] == 1.0
        assert result["signals"]["total_score"] == 0.0  # floor at 0


class TestBuildSignalProfile:
    def test_empty_profile_for_user_with_no_ratings(self, app):
        from models import db, User
        from routes.rec_signals import build_signal_profile
        u = User(email="new@x.com", username="newbie", password_hash="x")
        db.session.add(u)
        db.session.commit()
        profile = build_signal_profile(u.id)
        assert profile["rating_count_at_compute"] == 0
        assert profile["top_genres"] == []
        assert profile["top_studios"] == []
        assert profile["loved_examples"] == []
        assert profile["currently_watching"] == []
        assert profile["watchlist_planning_ids"] == []

    def test_extracts_top_studios_with_hit_rate(self, app):
        """User rated 3 MAPPA shows: 9, 8, 5. hit_rate = 2/3 ~ 0.667."""
        from models import db, User, Anime, Rating
        from routes.rec_signals import build_signal_profile
        u = User(email="r@x.com", username="rater", password_hash="x")
        db.session.add(u); db.session.commit()
        for i, score in enumerate([9, 8, 5]):
            a = Anime(title=f"MAPPA Show {i}", anilist_id=900 + i, studio="MAPPA")
            db.session.add(a); db.session.commit()
            db.session.add(Rating(user_id=u.id, anime_id=a.id, score=score))
        db.session.commit()
        profile = build_signal_profile(u.id)
        mappa = next((s for s in profile["top_studios"] if s["name"] == "MAPPA"), None)
        assert mappa is not None
        assert mappa["n"] == 3
        assert abs(mappa["hit_rate"] - 2/3) < 1e-3

    def test_loved_and_dropped_examples_populated(self, app):
        from models import db, User, Anime, Rating
        from routes.rec_signals import build_signal_profile
        u = User(email="r2@x.com", username="r2", password_hash="x")
        db.session.add(u); db.session.commit()
        loved = Anime(title="Frieren", anilist_id=701, studio="Madhouse")
        dropped_anime = Anime(title="Bad Show", anilist_id=702, studio="Other")
        db.session.add_all([loved, dropped_anime]); db.session.commit()
        db.session.add(Rating(user_id=u.id, anime_id=loved.id, score=9))
        db.session.add(Rating(user_id=u.id, anime_id=dropped_anime.id, score=3))
        db.session.commit()
        profile = build_signal_profile(u.id)
        assert any(e["title"] == "Frieren" for e in profile["loved_examples"])
        assert any(e["title"] == "Bad Show" for e in profile["dropped_or_low_examples"])


class TestScoreCandidates:
    def test_excludes_already_rated_anime(self, app):
        from models import db, User, Anime, Rating
        from routes.rec_signals import build_signal_profile, score_candidates
        u = User(email="sc@x.com", username="sc", password_hash="x")
        db.session.add(u); db.session.commit()
        rated = Anime(title="Rated Already", anilist_id=801, studio="Z")
        db.session.add(rated); db.session.commit()
        db.session.add(Rating(user_id=u.id, anime_id=rated.id, score=9))
        db.session.commit()
        # Add an unrated candidate so the result isn't empty
        unrated = Anime(title="Free", anilist_id=802, studio="Z")
        db.session.add(unrated); db.session.commit()

        profile = build_signal_profile(u.id)
        candidates = score_candidates(u.id, profile, limit=10, include_nsfw=False)
        ids = {c["id"] for c in candidates}
        assert rated.id not in ids
        assert unrated.id in ids

    def test_returns_sorted_by_total_score_desc(self, app):
        from models import db, User, Anime
        from routes.rec_signals import build_signal_profile, score_candidates
        u = User(email="sc2@x.com", username="sc2", password_hash="x")
        db.session.add(u); db.session.commit()
        for i in range(5):
            db.session.add(Anime(title=f"Cand {i}", anilist_id=850 + i, api_score=7 + i * 0.1))
        db.session.commit()
        profile = build_signal_profile(u.id)
        candidates = score_candidates(u.id, profile, limit=10, include_nsfw=False)
        totals = [c["signals"]["total_score"] for c in candidates]
        assert totals == sorted(totals, reverse=True)
