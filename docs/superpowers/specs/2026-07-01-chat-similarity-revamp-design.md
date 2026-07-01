# Chat recommendation revamp — seed-based similarity + full-signal LLM judgment

Status: approved (brainstorm 2026-07-01)
Extends: `2026-05-21-chat-rec-engine-design.md` (signal profile + grounded candidates — kept as-is; this spec layers seed-based similarity on top)

## 1. Goal

Make the chat able to answer "recommend me something like Re:Zero" at high
quality, and make every recommendation use the full picture of the user's
data. Concretely:

1. A deterministic **similarity engine**: given a seed anime, rank the whole
   catalog by shared DNA (tags, genres, format, era), personalized by the
   existing signal profile.
2. The engine powers three surfaces: a new **`GET /api/anime/<id>/similar`**
   endpoint, a **"More like this" strip** on anime detail pages, and a new
   **`find_similar_anime` chat tool** the LLM calls instead of improvising.
3. The chat LLM sees the **full signal picture** — watchlist by status,
   favorites, loved/dropped examples, era + episode preferences, and review
   text — in recommend *and* rate modes.
4. **No-repeat memory**: titles already suggested in the conversation are
   excluded from later turns, so refinements refine.

## 2. Non-goals

- No embedding/vector infrastructure. The similarity engine is metadata
  scoring; `utils/similarity.py` is the seam where embeddings could slot in
  later without touching callers.
- No collaborative filtering (user count is single-digit).
- No chat history persistence (conversations stay stateless; the frontend
  re-sends history).
- No changes to rate/onboard mode flows beyond context enrichment.

## 3. Architecture — retrieve, personalize, judge

```
user: "something like Re:Zero"
        │
        ▼
LLM (recommend mode) ── calls tool ──► find_similar_anime("Re:Zero")
        ▲                                   │
        │                          resolve seed (local fuzzy → AniList)
        │                                   ▼
        │                       utils/similarity.py: similar_to(seed)
        │                          1. tag/genre/format/era scoring
        │                          2. franchise exclusion
        │                          3. blend with rec_signals personal score
        │                          4. drop watched / suggested-this-chat
        │                                   │
        └──── ranked candidates + reasons ──┘
        │
        ▼
LLM picks 3, each anchored to evidence (shared tags + a personal signal)
        │
        ▼
existing **Title** → card resolution + validation (unchanged)
```

The LLM never ranks the catalog; it judges a pre-ranked shortlist and
explains. The engine never writes prose; it scores and excludes. The
existing grounding/validation pipeline in `routes/chatbot.py` is unchanged.

## 4. Data model — persist AniList tags

`utils/anilist.py::_normalize_anime` already extracts per-anime tags
(name, rank 0–100, category) but they are never stored. New tables in
`models.py`:

```python
class Tag(db.Model):
    __tablename__ = "tags"
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(80), unique=True, nullable=False, index=True)
    category = db.Column(db.String(80))          # AniList tag category

class AnimeTag(db.Model):                        # association object (rank per link)
    __tablename__ = "anime_tags"
    anime_id = db.Column(db.Integer, db.ForeignKey("anime.id"), primary_key=True)
    tag_id   = db.Column(db.Integer, db.ForeignKey("tags.id"), primary_key=True)
    rank     = db.Column(db.Integer, nullable=False)   # 0-100 relevance
```

- Sync rule: persist tags with `rank >= 40` (lower than the current 60
  extraction filter — similarity benefits from breadth; <40 is noise).
  Skip tags flagged `isAdult` by AniList.
- Upsert lives in the same path as genre upserts in `sync_anilist.py`;
  re-sync replaces an anime's tag links.
- **Backfill**: the existing weekly full resync repopulates tags; prod is
  backfilled once via `fly ssh console` running the sync (see
  `docs/runbooks/catalog-backfill.md` pattern). No new migration framework —
  tables created via the existing ad-hoc migrate-script pattern
  (`migrate_watchlist.py` precedent).

## 5. Similarity engine — `utils/similarity.py`

Pure functions, no Flask imports, fully unit-testable.

### 5.1 Unpersonalized similarity (seed → candidate, score ∈ [0, 100])

| component        | weight | definition |
|------------------|--------|------------|
| tag_overlap      | 45     | weighted Jaccard over tag vectors `{name: rank/100}`: `Σ min(a,b) / Σ max(a,b)` over the union |
| genre_overlap    | 20     | Jaccard over official genre name sets |
| fan_genre_overlap| 10     | Jaccard over top-5 aggregated fan genres (`Anime.get_fan_genres()`) |
| format_fit       | 10     | mean of two binaries: same source bucket (manga / LN+novel / original / other), same episode bucket (≤13 / 14–26 / >26) |
| quality_prior    | 10     | `max(api_score, community_score) / 10` — ranking prior so results aren't obscure junk |
| era_proximity    | 5      | `exp(-(Δyear)² / (2·8²))` |

- **Tagless seed fallback** (not yet backfilled): redistribute the 45-point
  tag weight proportionally across the remaining components.
- **Hard exclusions before scoring**: the seed itself, NSFW hard-blocked
  genres, same-franchise entries (§5.2).

### 5.2 Franchise exclusion

Primary: franchise ID set from the existing `assemble_franchise()` BFS
(already cached ~2h in the `/related` path). Fallback when AniList is
unreachable: normalized title-root heuristic (strip season/part/ordinal/
"OVA"/"movie" suffixes; match on root). Excluded entries are returned in a
separate `franchise` list (filtered to unwatched) so surfaces can say
"you also haven't seen Re:Zero S3" without spending similarity slots.

### 5.3 Personalization blend

When `user_id` is provided:

```
final = 0.7 * similarity + 0.3 * rec_signals.score_candidate(profile, anime)
```

plus hard exclusions: anything the user has rated or has on the watchlist
in any status except `plan_to_watch` (plan-to-watch items stay, flagged
`in_plan_to_watch: true` — "you already planned this one" is a feature).
The dropped-trait penalty rides in via `score_candidate`. Anonymous
callers get pure similarity.

### 5.4 Performance

In-process tag index `{anime_id: {tag: rank}}` built lazily on first use,
refreshed when older than 6h (catalog syncs are weekly; 6h is generous).
Full-catalog scan (~4–6k rows) in Python is O(n) dict math — target
< 300 ms warm for `/similar`. Per-seed unpersonalized rankings cached in an
LRU (`maxsize=512`); personalization applied after cache retrieval.

## 6. API surface — `GET /api/anime/<id>/similar`

- Query: `limit` (default 12, max 24), `include_nsfw` (same semantics as
  other anime endpoints). Auth optional — JWT present ⇒ personalized blend.
- Response:

```json
{
  "seed": {card fields},
  "similar": [{card fields, "match_score": 0-100, "shared_tags": ["Isekai", "Time Loop"], "in_plan_to_watch": false}],
  "franchise": [{card fields}]
}
```

- Note: `frontend/src/lib/api.ts` already defines `getSimilar()` and a
  `SimilarResponse` type — the backend route is the missing half. Audit
  existing frontend consumers of `getSimilar` before reusing/adjusting the
  response type.

## 7. Chat upgrades

### 7.1 New tool: `find_similar_anime` (`utils/ai_tools.py` + executor in `routes/chatbot_tools.py`)

```
find_similar_anime(
  title: str,            # required; resolver: exact → fuzzy local → AniList search fallback
  mood_tags: [str],      # optional; boost candidates carrying these tags ("darker" → Tragedy, Psychological)
  exclude_ids: [int],    # optional; on top of automatic no-repeat exclusions
  limit: int = 8,
)
```

Returns JSON: resolved seed + ranked candidates, each with `id, title, year,
genres, shared_tags, match_score`, and `personal_fit` notes ("matches your
top genre Psychological", "in your plan-to-watch"). If the seed resolves
only via AniList (not in local catalog), similarity falls back to the
AniList entry's genre/tag payload for the seed vector.

### 7.2 Full-signal context (`routes/chat_context.py`)

Extend the context JSON injected for authenticated users — and inject it in
**rate mode too**, not just recommend:

- `watchlist`: titles grouped by status (watching / completed / dropped /
  on_hold / plan_to_watch), capped 15 per group.
- `favorites`: favorited titles.
- `loved_examples` / `dropped_examples`: `{title, score}` (already in the
  signal profile).
- `era_lean_year`, `episode_fit_pref` (already computed).
- `reviews`: top 5 by signal strength (`|score − 5.5|` desc):
  `{title, score, snippet}` — snippet = first 280 chars.
- Budget: total context JSON ≤ 8 KB; truncate group lists before reviews,
  reviews before candidates.

### 7.3 No-repeat memory (`routes/chatbot.py`)

Parse prior **assistant** turns of the incoming conversation with the
existing `_BOLD_TITLE_RE`, resolve to anime IDs, and:
- exclude them from candidate building and `find_similar_anime` defaults,
- drop them in the post-LLM validation pass,
- add a system-prompt rule: never re-suggest a title already shown in this
  conversation unless the user asks about it by name.

Stateless — derived from the re-sent history, no schema change.

### 7.4 Judgment prompt rewrite (`routes/chatbot_tools.py`)

`MODE_PROMPTS["recommend"]` gains:
1. If the user names a specific anime as reference, call
   `find_similar_anime` — do not improvise similarity.
2. Every pick must cite evidence: at least one shared tag/genre with the
   seed AND (when signals exist) one personal signal ("you rated
   Steins;Gate 10").
3. Refinements ("darker", "shorter", "older") re-call the tool with
   `mood_tags`/adjusted filters instead of re-ranking from memory.
4. Franchise siblings are never "similar" picks; mention unwatched ones in
   prose only.
5. Word cap raised 80 → 100 to fit evidence-anchored reasons; 3 cards max
   and [OPTIONS] pill rules unchanged.

## 8. Frontend

- **"More like this" strip** on `AnimeDetailPage`: below/beside the
  existing franchise strip; reuses the `AnimeCard` grid; renders
  `shared_tags` as small badges; hidden entirely when `similar` is empty.
- **For You row**: `/api/recommend/for-me` response gains an optional,
  additive `because_you_loved: {seed: {...}, items: [...]}` built from the
  user's highest-rated tagged title; `ForYouPage` renders it as one row of
  6 when present.

## 9. Testing strategy

TDD throughout (house rule):
- `tests/test_similarity.py`: tag overlap math, weight blend, tagless-seed
  fallback, franchise exclusion (both paths), personalization blend +
  exclusions, tag index refresh.
- `tests/test_anime_tags_sync.py`: tag persistence, rank filter, adult-tag
  skip, re-sync replaces links.
- `tests/test_similar_endpoint.py`: response shape, limit clamp, NSFW
  filter, anonymous vs authed ranking difference, 404 on unknown id.
- `tests/test_chatbot_tools.py` (extend): `find_similar_anime` executor —
  resolution fallbacks, mood_tags boost, exclusions honored.
- `tests/test_chat_context.py` (extend): watchlist groups, review
  snippets, size budget truncation, rate-mode injection.
- `tests/test_chatbot.py` (extend): no-repeat extraction from history,
  validation drops repeats.
- Frontend vitest: similar strip renders/hides, For You row renders when
  present.
- Live smoke after deploy: the Re:Zero success criterion below, via demo
  login.

## 10. Risks

- **Tag coverage after backfill**: some catalog entries (donghua, very new
  seasons) may have few tags → tagless fallback must degrade gracefully
  (tested).
- **AniList dependency for franchise exclusion**: mitigated by the
  title-root fallback; /similar never blocks on AniList.
- **Prompt regression in other modes**: rate/onboard prompts assert-tested
  to not gain recommendation behavior.
- **SQLite table creation on prod**: create-tables script must be
  idempotent and run before the backfill sync (runbook order).

## 11. Success criteria

1. Chat: "recommend me anime similar to Re:Zero" (as demo user) returns 3
   cards — no Re:Zero-franchise entries, nothing already watched/rated,
   each sharing ≥ 2 meaningful tags with the seed, each with a reason
   citing a shared tag and a personal signal.
2. "Something else, darker" in the same conversation returns 3 *new* cards
   skewed to Tragedy/Psychological/Horror tags.
3. `GET /api/anime/<re-zero-id>/similar` returns a sensible ranked list in
   < 300 ms warm on prod.
4. Detail pages show a "More like this" strip for tagged anime.
5. Full backend + frontend suites green; deployed to Fly; prod tags
   backfilled.

## 12. Confirmed decisions (from brainstorm)

- Hybrid engine: metadata similarity retrieval + existing `rec_signals`
  personalization + improved LLM judgment on top (user choice).
- Scope: chat + site-wide (`/similar` endpoint, detail strip, For You row).
- All four extras approved: full-signal context, no-repeat/refinement
  memory, review text in context, franchise-aware answers.
- No embeddings in this iteration; design leaves the seam.
