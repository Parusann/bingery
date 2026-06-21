# Season-aware Dub Matching (Sub-projects B+C) — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/schedule-season-matching`

## Context

Schedule-accuracy sub-project. Originally split as B (episode numbers) and C
(season identity); on inspection B's value (per-season renumbering) was small and
its cost (schema migration) high, and it overlapped C, so **B and C are merged**
and B's schema work is **dropped**. This sub-project fixes the "wrong season
shown" complaint via correct dub-to-season attachment. (A = freshness shipped in
PR #12; D = dub *date* estimation is next.)

## Problem

A dub feed entry titled e.g. "My Hero Academia Season 7" is written onto the
**Season 1** `Anime` row, so the schedule shows the dub under the wrong season.

## Root cause (verified)

AniList stores each season as a **separate Media** → a separate `Anime` row with
its own `anilist_id` and a title that usually contains the season ("... Season 7").
The dub matcher `best_match` in `utils/dub_sources/crunchyroll.py`:
- `SEASON_SUFFIX_RE` + `_strip_season()` remove `season N` / `sN` / `part N` /
  `cour N` from **both** the feed title (`norm_query`, ~line 181) **and every
  candidate** (~line 194) before fuzzy-matching with `rapidfuzz`
  `token_set_ratio`.
- So "My Hero Academia Season 7" and the S1 row both collapse to "My Hero
  Academia"; `extractOne` picks whichever scores first — usually the base/S1 row.

`utils/dub_sources/animeschedule.py` imports and reuses `best_match`, so both dub
sources share the bug. The existing test
`tests/test_dub_crunchyroll.py::test_best_match_strips_season_suffix` *asserts*
the stripping behavior and must be reversed.

## Goals

Dub feed entries attach to the **correct season's** `Anime` row, so the schedule
shows the right season. Wrong-season attachment should fail to "no dub written"
rather than "wrong-season dub written."

## Non-goals

- Episode-number renumbering / `Episode` schema change (dropped — AniList already
  stores seasons as separate rows; absolute numbers like One Piece "EP 1088" are
  correct; the season is carried by the row's title shown on the schedule).
- UI changes (the correct row's title already shows the season).
- Dub *date* estimation accuracy (sub-project D).
- Sub (AniList) episode handling — already per-Media-correct.

## Approach: full-title matching + season guard

Rewrite `best_match` to match on **full titles** and use the season number as a
guard rather than stripping it away:

- `_parse_season(title) -> int` (default `1`): parse `season N`, `Nth season`,
  `part N`, `cour N`, `sN` (case-insensitive). Absence ⇒ season 1.
- For each candidate `Anime`, for each non-empty title field (`title`,
  `title_english`): `score = token_set_ratio(feed_lower, field_lower)`; if
  `_parse_season(field) != _parse_season(feed_title)` subtract a fixed penalty
  (`SEASON_MISMATCH_PENALTY = 35`). Track the highest-scoring `(anime, score)`.
- Keep returning `(anime, score)`; the caller's existing minimum-score acceptance
  threshold is unchanged. A candidate that matches only because seasons were
  collapsed now scores lower (penalty) and may fall below threshold ⇒ no dub
  written (the correct, safe failure mode).

Why this works: token_set_ratio of "my hero academia season 7" vs the S1 title
"my hero academia" is high (subset), but the season mismatch penalty drops it
below the true "... Season 7" row, which scores high with no penalty. A
no-season feed (season 1) still matches the base row (both season 1, no penalty).

Keep `SEASON_SUFFIX_RE`/`_strip_season` only if still referenced elsewhere;
otherwise remove the now-dead `_strip_season`.

## Components

- `utils/dub_sources/crunchyroll.py` — add `_parse_season` +
  `SEASON_MISMATCH_PENALTY`; rewrite `best_match` to full-title + season-guard.
- `utils/dub_sources/animeschedule.py` — no change (reuses `best_match`); verify
  the import still resolves.
- `tests/test_dub_crunchyroll.py` — reverse `test_best_match_strips_season_suffix`
  (a "Season 7" feed must select the Season-7 row, not the base) and add cases.

## Testing

- A "... Season 2" feed selects the Season-2 `Anime` row over the base/S1 row when
  both are candidates.
- A no-season feed selects the base (season-1) row.
- `part N` / `cour N` parse to the right season number (e.g. a "Part 2" feed
  doesn't match a "Part 1"/base row when a "Part 2" row exists).
- `_parse_season` unit cases: "Show", "Show Season 3", "Show 3rd Season",
  "Show Part 2", "Show Cour 2", "Show S2" → 1,3,3,2,2,2.
- Existing dub tests stay green except the intentionally-reversed one; full
  `pytest` suite green.

## Rollout / risk

Riskiest change in the fix-list — fuzzy matching is sensitive and AniList season
titles vary in format ("7th Season", romaji "... 7", etc.), so the season guard
can't be perfect. Mitigations: the penalty only *demotes* season mismatches (it
never forces a match that wasn't already textually similar); unmatched entries
safely write no dub; thorough matcher tests. No schema/migration, so it's
fully reversible by reverting the matcher. Behavior is identical for
single-season shows (the common case): season 1 vs season 1, no penalty.
