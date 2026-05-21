# Chat recommendation engine — multi-signal candidate retrieval + grounded LLM picks

**Date:** 2026-05-21
**Status:** Approved for implementation planning
**Author:** brainstormed with the user; written by the assistant

---

## 1. Goal

Make Bingery's AI chat recommendations feel **personalized to the specific user**, not generic-popular. The current pipeline gives the LLM a thin taste profile (top 5 genres, avg score, total rated) and trusts it to "know" anime. It falls back to populist picks (Demon Slayer / AoT / JJK) and writes vague reasons.

The new pipeline:

1. Computes a richer **signal profile** for the user (studio affinity, fan-genre clusters, dropout patterns, episode-fit, etc.) and caches it.
2. Pre-retrieves a **scored candidate set** of 30–50 unwatched anime using SQL + Python multi-signal scoring.
3. Calls the LLM with the chat message, the signal profile, AND the candidates JSON. The LLM is forced to pick from candidates and cite a specific signal from each pick's `signals` object as the reason.
4. Backend validates picks against the candidate set before returning to the client (no hallucinated titles).

Result: picks are grounded in a curated set the LLM didn't generate; reasons are grounded in numeric signals; obscure-but-fitting gems surface via a `surprise_factor` signal.

## 2. Non-goals

- **No embedding model.** Saved for a later phase. All scoring is SQL + Python.
- **No tool-calling / function-calling.** Gemma's tool-use is unreliable; we get the same effect by pre-computing the context.
- **No UI changes.** Response shape (`{response, suggested_anime, suggested_actions}`) stays identical.
- **No new external services.** Same Ollama + same Flask + same SQLite.
- **No re-architecting the `Rate` or `Onboard` chat modes' UX.** They reuse the new signal profile but skip candidate retrieval (they don't recommend).

## 3. Architecture

```
POST /api/chat/message
        │
        ▼
[1] Load user signal profile (cached on User.taste_profile_cache; lazy-recomputed
    if stale)
        │
        ▼
[2] If mode == "recommend":
        run candidate scorer → top 30–50 unwatched anime + per-signal scores
    Else (rate / onboard):
        no candidates; LLM uses signal profile alone for grounding
        │
        ▼
[3] Build LLM context JSON: { mode, user_message, user: signal_profile,
                              candidates: [...] (recommend only) }
        │
        ▼
[4] Call Ollama with BINGERY_SYSTEM + mode prompt + context JSON
        │
        ▼
[5] Parse LLM output → validate: any anime named in response.suggested_anime
    must be in candidate set. Drop hallucinated titles silently.
        │
        ▼
[6] Return {response, suggested_anime, suggested_actions} to client
```

The flow is **single-pass**. No retries, no second LLM call. The model gets enough context to do the right thing in one shot.

## 4. User signal profile

### 4.1 Schema (Python dict; JSON-serializable for caching)

```python
{
  "computed_at": "2026-05-21T04:30:00Z",
  "rating_count_at_compute": 33,    # used for cache invalidation
  "top_genres": [["Drama", 4.2], ["Slice of Life", 3.1], ...],   # max 8
  "top_studios": [                                                # max 5
    {"name": "MAPPA", "hit_rate": 0.83, "n": 6},
    {"name": "Kyoto Animation", "hit_rate": 0.71, "n": 7}
  ],
  "fan_genre_clusters": [["melancholy", 4], ["talky", 3]],        # max 8
  "era_lean_year": 2018,                                           # weighted-avg release year of liked set
  "episode_fit_pref": {                                            # buckets: short / medium / long
    "short": 0.45,   # share of completed shows with <=13 ep
    "medium": 0.40,  # 14-26
    "long": 0.15     # >26
  },
  "dropped_traits": {
    "studios": ["X Studio", "Y Studio"],
    "genres": ["Ecchi", "Sports"]
  },
  "loved_examples": [                                              # max 5
    {"title": "Frieren", "score": 9.5},
    {"title": "Violet Evergarden", "score": 9.0}
  ],
  "dropped_or_low_examples": [                                     # max 3
    {"title": "X", "score": 4.0}
  ],
  "currently_watching": ["Apothecary Diaries"],                    # title strings, max 3
  "watchlist_planning_ids": [123, 456, 789]                        # anime IDs, max 20
}
```

### 4.2 Computation

`build_signal_profile(user_id) -> dict` lives in `routes/rec_signals.py`. Pure function over the user's `Rating`, `FanGenreVote`, `WatchlistEntry` tables joined with `Anime`. Recomputation cost target: <500ms for a heavy user (Mio: 33 ratings → ~50ms expected).

### 4.3 Cache

New column: `User.taste_profile_cache TEXT NULL` (SQLite JSON).

Invalidation: **lazy**. On `GET signal_profile`:
```python
cached = json.loads(user.taste_profile_cache) if user.taste_profile_cache else None
current_count = Rating.query.filter_by(user_id=user.id).count()
if not cached or cached["rating_count_at_compute"] != current_count:
    cached = build_signal_profile(user.id)
    user.taste_profile_cache = json.dumps(cached)
    db.session.commit()
return cached
```

The trigger is "rating count changed since last compute". For a watchlist-only change (no rating), we skip recompute — watchlist data is small enough to re-fetch fresh on every call (it's a single query). This keeps the cache cheap and the invariant simple.

## 5. Candidate scoring

### 5.1 Exclusions (hard filter — applied before scoring)

A candidate must NOT:
- Have a Rating row from this user (any score)
- Be in WatchlistEntry with status ∈ {`watching`, `completed`, `dropped`, `on_hold`}
  - `planning` status is **allowed** (the user wants to watch it; we may rank them up)
- Belong to NSFW hard-blocked genres (`Hentai`) — reuse `utils.nsfw.HARD_BLOCKED_GENRES`
- Match soft-blocked genres (`Ecchi`) unless the request includes the NSFW opt-in flag

### 5.2 Scoring formula (per candidate, score ∈ [0, 100])

```
score =  25 * studio_affinity         # in [0, 1]
       + 20 * genre_match             # weighted Jaccard, [0, 1]
       + 15 * fan_genre_match         # [0, 1]
       + 10 * era_fit                 # gaussian around user's era_lean_year, [0, 1]
       + 10 * episode_fit             # match episode count to user's bucket prefs, [0, 1]
       + 10 * surprise_bonus          # api_score >= 8 AND popularity_rank > 100, [0, 1]
       +  5 * watchlist_coherence     # 1 if planning, else 0
       - 20 * dropped_trait_penalty   # share of candidate's studios+genres in dropped_traits, [0, 1]
```

### 5.3 Signal definitions

- **`studio_affinity`** = `user.top_studios[candidate.studio].hit_rate` if present else `0`. Tie-break: if the user has 0 ratings for this studio, treat as `0.0` (unknown, not bad).
- **`genre_match`** = `sum(user.top_genres[g].weight for g in candidate.genres) / sum_of_all_user_weights`. Bounded to [0, 1].
- **`fan_genre_match`** = same shape but over fan_genre_clusters.
- **`era_fit`** = `exp(-((candidate.year - user.era_lean_year)^2) / (2 * 6^2))` — a Gaussian with σ=6 years.
- **`episode_fit`** = look up the user's `episode_fit_pref` bucket share for the candidate's episode count.
- **`surprise_bonus`** = `1.0` if `candidate.api_score >= 8 AND candidate.popularity_rank > 100`, `0.5` if score≥8 OR rank>100, else `0`. (We don't have popularity_rank yet — see §10.1.)
- **`watchlist_coherence`** = `1` if `candidate.id in user.watchlist_planning_ids`, else `0`.
- **`dropped_trait_penalty`** = `(1 if candidate.studio in dropped_traits.studios else 0) * 0.5 + (overlap_count(candidate.genres, dropped_traits.genres) / max(1, len(candidate.genres))) * 0.5`.

### 5.4 Return shape

`score_candidates(user_id, signal_profile, limit=40, include_nsfw=False) -> list[dict]`:

```python
[
  {
    "id": 21459,
    "title": "Showa Genroku Rakugo Shinju",
    "year": 2016,
    "studio": "Studio DEEN",
    "genres": ["Drama", "Historical"],
    "fan_genres": ["melancholy", "talky"],
    "api_score": 8.6,
    "image_url": "...",
    "signals": {
      "studio_affinity": 0.0,
      "genre_match": 0.78,
      "fan_genre_match": 0.91,
      "era_fit": 0.65,
      "episode_fit": 0.80,
      "surprise_factor": 0.85,
      "watchlist_aligned": 0,
      "dropped_trait_penalty": 0.0,
      "total_score": 73.4
    }
  }
]
```

Sorted by `total_score` descending. Limit defaults to 40; raise to 80 only for the "no taste profile yet" cold-start path so the LLM has more breathing room.

## 6. LLM context

### 6.1 Context JSON sent in the system prompt

```json
{
  "mode": "recommend",
  "user_message": "I want something melancholy",
  "user": <signal_profile, MINUS the cache-only fields like computed_at>,
  "candidates": <output of score_candidates() — only when mode == "recommend">
}
```

For `rate` / `onboard` modes, omit `candidates` entirely. The signal profile + chat history is enough.

### 6.2 Prompt additions

Two clauses appended to BINGERY_SYSTEM (after the existing length rules, before the mode prompt):

```
# GROUNDING RULES (CRITICAL — only apply when `candidates` is present)
1. Your `suggested_anime` MUST be selected ONLY from the `candidates` array
   provided in the context JSON. You may not name an anime not in that list.
   If no candidate fits the user's vibe, say so honestly and ask a follow-up
   — do not invent.
2. For each suggested anime, your reason MUST cite the single highest-value
   signal from that candidate's `signals` object, framed in human terms.
   Examples:
     signals.fan_genre_match=0.91 → "matches your melancholy + talky cluster"
     signals.studio_affinity=0.83 → "from MAPPA, where you've loved 5 of 6"
     signals.surprise_factor=1.0  → "underrated gem outside the top-100"
   Do not invent reasons.
```

### 6.3 Validation pass (post-LLM)

In `routes/chatbot.py`:

```python
candidate_ids = {c["id"] for c in context["candidates"]}
filtered = [s for s in parsed_response.suggested_anime if s.id in candidate_ids]
if len(filtered) < len(parsed_response.suggested_anime):
    logger.warning("LLM hallucinated %d titles; filtered out",
                   len(parsed_response.suggested_anime) - len(filtered))
parsed_response.suggested_anime = filtered
```

Silent drop. If all picks were hallucinated (rare), `suggested_anime` is empty and the frontend just shows the text response.

## 7. Implementation surface

### 7.1 New files

- `routes/rec_signals.py`
  - `build_signal_profile(user_id) -> dict`
  - `score_candidates(user_id, signal_profile, limit=40, include_nsfw=False) -> list[dict]`
  - All helper functions are module-private and pure (no DB writes; reads are explicit).
- `routes/chat_context.py`
  - `build_llm_context(user_id, message, mode, include_nsfw) -> dict`
  - Pulls signal profile (via cache), runs `score_candidates` if mode requires.
- `tests/test_rec_signals.py`
  - Unit tests for each signal scorer (pure functions)
  - Integration test: seeded user + fixture anime → expected top-N
- `tests/test_chat_context.py`
  - Snapshot test for the JSON shape passed to the LLM

### 7.2 Modified files

- `routes/chatbot.py`
  - Replace ad-hoc taste-profile fetch with `build_llm_context(...)`
  - Add post-LLM validation pass against `candidates`
  - Same ProviderUnavailableError handling stays
- `routes/chatbot_tools.py`
  - Append GROUNDING RULES to `BINGERY_SYSTEM`
  - The `MODE_PROMPTS` stay; this composes ABOVE them
  - Stop computing taste_profile inline — receive it via context
- `routes/recommend.py`
  - `/api/recommend/for-me` route uses the new `score_candidates` for consistency. The response shape stays `{anime, reason, relevance_score}` per pick — we just compute reasons from the signal that drove the pick, same as the LLM is told to.
- `models.py`
  - Add `User.taste_profile_cache = db.Column(db.Text, nullable=True)`. The project has no migrations framework; schema is managed by SQLAlchemy `create_all()` on boot. The implementation plan will issue a one-shot `ALTER TABLE user ADD COLUMN taste_profile_cache TEXT` against the live SQLite via `flyctl ssh console` (and the same against local `bingery.db`) since `create_all` doesn't add columns to existing tables.

### 7.3 Data model migration

One nullable column. SQLite `ALTER TABLE user ADD COLUMN taste_profile_cache TEXT` is safe in-place. No downtime.

## 8. Mode-specific behavior

| Mode | Signal profile? | Candidates? | LLM job |
|---|---|---|---|
| `recommend` | yes | yes (40) | pick 2-3 from candidates; cite signals |
| `rate` | yes | no | ask reflective questions grounded in the user's history |
| `onboard` | yes (may be sparse) | no | elicit 3 loves + 2 dislikes; never name shows |

For `rate` and `onboard`, the LLM gets `user.loved`, `user.dropped_or_low`, `user.currently_watching` so it can refer to those titles by name without hallucinating ("How did you feel about *Frieren*'s ending?"). The guardrail there is different: "Only reference anime titles that appear in the `user` block — do not name others."

## 9. Performance budget

| Stage | Budget | Notes |
|---|---|---|
| Signal profile lookup | <50ms (cache hit) / <500ms (miss) | One user; cache miss is rare |
| Candidate scoring | <200ms | ~15k anime, all in-memory scoring after one SQL pull |
| LLM call | 8-15s | Unchanged; dominates round-trip |
| Validation pass | <5ms | Set membership check |
| **Total added vs today** | **<250ms** | Negligible vs the LLM hop |

If the SQL pull of all candidate anime turns out to be slow on Fly's shared CPU, switch to a paginated scoring approach (score top-200-by-api_score first, then top-200 by recency, dedupe). Optimization deferred to the implementation plan if measurement shows it's needed.

## 10. Open risks / things to watch

### 10.1 `popularity_rank` doesn't exist on the Anime model yet
The `surprise_factor` signal needs popularity data. Options for the plan:
- Use `api_score`-based proxy: `popularity_proxy = (10 - api_score) * some_inverse_function_of_rating_count` — terrible.
- Add a `popularity_rank` column populated from AniList during the existing sync. Cleanest, requires a sync script change.
- Skip surprise_factor in v1; revisit. Acceptable but loses one of the more impactful signals.

**Decision in spec: pick "Add `popularity_rank` column" — the AniList API exposes it, and the sync already runs.** Plan will detail the sync change.

### 10.2 LLM still hallucinates despite the rule
Mitigation: the validation pass silently drops hallucinations. If the empty `suggested_anime` problem persists, we'd add a second LLM call ("here's your draft; rewrite using only these IDs"). Not in v1.

### 10.3 Cold-start (new user with 0 ratings)
The signal profile is mostly empty. `score_candidates` falls back to: `studio_affinity = 0` for all, `genre_match` driven only by chat-message keyword extraction (parsed in Python: extract genre nouns from `user_message` and treat them as `top_genres` with weight 1.0 for this call). Surprise factor and api_score dominate. Result: better than the current cold-start (which just throws popular shows) but not great. Acceptable.

### 10.4 Signal profile data drift
If we add a signal, `rating_count_at_compute`-based invalidation won't trigger. Add a `SIGNAL_PROFILE_SCHEMA_VERSION` constant in `rec_signals.py`; cache invalidates if the stored version differs.

## 11. Testing strategy

- **Unit (pure functions):** each signal scorer gets ≥3 cases — typical, edge (empty input), boundary.
- **Integration:** fixture user with 10 ratings, 3 watchlist entries; assert `score_candidates` returns expected shape + ordering for a known input.
- **Snapshot:** `build_llm_context(...)` output JSON committed as a fixture; tests catch unintended shape changes.
- **E2E (existing pytest):** the existing chat happy-path tests stay; one new test asserts every `suggested_anime.id` in the response is in the synthetic candidate set.

## 12. Out of scope (for explicit clarity)

- Embeddings / vector similarity (saved for phase 2)
- LLM tool-calling
- Real-time profile updates as user rates *during* a chat session (next conversation will pick up new data; mid-conversation rating won't reroute the current turn)
- A "more like this" follow-up after a pick is rejected (would be a great phase 2 feature: feed the rejection signal back into a re-score)
- Multi-model support (e.g., bigger model for re-rank step) — single Ollama call stays
- Changes to the Anthropic provider (the Ollama provider is the production path; Anthropic stays as a dev fallback)

## 13. Success criteria

Subjective (judged by the user on the demo dataset):
- 3 sample queries — "something melancholy", "I'm in a shonen mood", "surprise me" — produce picks that the user wouldn't have seen in the current populist set.
- The reason text for each pick cites a specific signal (studio, fan-genre, surprise) with a number, not vibes.

Objective:
- Zero hallucinated titles in 20 consecutive chat sessions (validation pass works).
- Round-trip latency stays within +250ms of today's baseline.
- Test suite: 220 existing tests still pass; ≥15 new tests for the rec engine.

## 14. Confirmed decisions (from brainstorm)

1. ✅ Exclude completed/dropped/rated titles entirely from candidates; surface them in `user.loved` / `user.dropped_or_low` instead.
2. ✅ `Rate` / `Onboard` modes reuse the signal profile but skip candidate retrieval.
3. ✅ Lazy cache invalidation (recompute on first chat after a rating change).
4. ✅ Unify `/api/recommend/for-me` on the same scorer for consistency between chat and the For You page.
