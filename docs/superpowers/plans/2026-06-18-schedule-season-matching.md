# Season-aware Dub Matching (B+C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dub feed entries attach to the correct season's `Anime` row (fixing "wrong season shown"), by replacing the season-stripping fuzzy matcher with full-title matching + a season-number guard.

**Architecture:** Rewrite `best_match` in `utils/dub_sources/crunchyroll.py` (reused by `animeschedule.py`). Score full titles with rapidfuzz `process.extract` (top-k, in C), then re-rank the top candidates with a penalty when the candidate's parsed season ≠ the feed's; return the adjusted score so the caller's existing threshold rejects season-only mismatches (safe failure = no dub written).

**Tech Stack:** Python, rapidfuzz, pytest.

Spec: `docs/superpowers/specs/2026-06-18-schedule-season-matching-design.md`
Branch: `feat/schedule-season-matching`

**Conventions:** NO AI attribution in commits. No schema/UI change. Edit via desktop-commander/Grep when native Read is truncated.

---

## Verified facts
- `best_match(show_title, candidates)` currently `_strip_season()`s both the query and every candidate, flattens `(anime, title-field)` → `titles`/`owners`, and `rapidfuzz.process.extractOne(norm_query, titles, scorer=token_set_ratio)`; returns `(owner, score)`.
- Caller `ingest_feed` (same file): `anime, score = best_match(...)`; rejects when `anime is None or score < threshold` (`threshold=MATCH_THRESHOLD`). Candidates are `_AnimeCand(id, title, title_english)` namedtuples.
- `animeschedule.py` imports `best_match` and reuses it (no change needed).
- `tests/test_dub_crunchyroll.py::test_best_match_strips_season_suffix` asserts the OLD stripping behavior and must be reversed.

---

## Task 1: Season-aware `best_match`

**Files:** `utils/dub_sources/crunchyroll.py`; test `tests/test_dub_crunchyroll.py`

- [ ] **Step 1: Read the exact current `best_match`, `MATCH_THRESHOLD`, and `test_best_match_strips_season_suffix`** (so the rewrite preserves the signature/return and the test reversal uses the file's existing `_AnimeCand`/anime stub pattern). `grep -n "MATCH_THRESHOLD" utils/dub_sources/crunchyroll.py`.

- [ ] **Step 2: Write the new/updated tests** in `tests/test_dub_crunchyroll.py`. Reverse the stripping test and add coverage. Use the file's existing way of building candidate anime (a small namedtuple/obj with `.title` and `.title_english`); if it uses a helper, reuse it. Example shape:
  ```python
  from utils.dub_sources.crunchyroll import best_match, _parse_season

  class _Cand:
      def __init__(self, title, title_english=None):
          self.title = title
          self.title_english = title_english

  def test_parse_season_variants():
      assert _parse_season("My Hero Academia") == 1
      assert _parse_season("My Hero Academia Season 7") == 7
      assert _parse_season("My Hero Academia 3rd Season") == 3
      assert _parse_season("Show Part 2") == 2
      assert _parse_season("Show Cour 2") == 2
      assert _parse_season("Show S2") == 2
      assert _parse_season("Mob Psycho 100") == 1  # bare number is not a season

  def test_best_match_picks_correct_season_not_base():
      base = _Cand("My Hero Academia")
      s7 = _Cand("My Hero Academia Season 7")
      anime, score = best_match("My Hero Academia Season 7", [base, s7])
      assert anime is s7

  def test_best_match_no_season_picks_base():
      base = _Cand("My Hero Academia")
      s7 = _Cand("My Hero Academia Season 7")
      anime, _ = best_match("My Hero Academia", [base, s7])
      assert anime is base

  def test_best_match_part_distinguishes():
      p1 = _Cand("Attack on Titan")
      p2 = _Cand("Attack on Titan Part 2")
      anime, _ = best_match("Attack on Titan Part 2", [p1, p2])
      assert anime is p2

  def test_best_match_wrong_season_only_scores_below_base_match():
      # Feed is S7 but only the base row exists -> demoted score (penalty),
      # so an exact base-title feed scores strictly higher than a season-
      # mismatched one. Guards the "safe failure" property.
      base = _Cand("My Hero Academia")
      _, s7_score = best_match("My Hero Academia Season 7", [base])
      _, base_score = best_match("My Hero Academia", [base])
      assert base_score > s7_score
  ```
  Then DELETE or rewrite `test_best_match_strips_season_suffix` so it no longer asserts stripping (it now asserts season-aware selection). Run `python -m pytest tests/test_dub_crunchyroll.py -k "season or parse or best_match" -v` → the new ones FAIL (`_parse_season` missing / old behavior).

- [ ] **Step 3: Implement.** In `utils/dub_sources/crunchyroll.py`, add near `SEASON_SUFFIX_RE`:
  ```python
  # Parse a season number from a title. Absence => season 1.
  SEASON_NUM_RE = re.compile(
      r"\b(?:season|part|cour)\s*(\d+)\b"
      r"|\b(\d+)(?:st|nd|rd|th)\s+season\b"
      r"|\bs(\d+)\b",
      re.IGNORECASE,
  )
  # How much to demote a candidate whose season differs from the feed's.
  SEASON_MISMATCH_PENALTY = 35.0


  def _parse_season(title: str) -> int:
      if not title:
          return 1
      m = SEASON_NUM_RE.search(title)
      if not m:
          return 1
      num = m.group(1) or m.group(2) or m.group(3)
      try:
          return int(num)
      except (TypeError, ValueError):
          return 1
  ```
  Replace the body of `best_match` with the full-title + season-guard version (keep the signature and the lazy rapidfuzz import):
  ```python
  def best_match(show_title: str, candidates: Iterable) -> tuple[Optional[object], float]:
      """Pick the Anime whose (title|title_english) best matches the feed title,
      using full titles + a season-number guard so a later-season feed can't
      collapse onto the base/Season-1 row.

      Returns (anime, adjusted_score). The score is demoted when the chosen
      candidate's season differs from the feed's, so the caller's acceptance
      threshold rejects season-only mismatches (no dub written).
      """
      from rapidfuzz import fuzz as _rf_fuzz
      from rapidfuzz import process as _rf_process

      query = (show_title or "").strip()
      if not query:
          return None, 0.0
      query_season = _parse_season(query)

      candidates = list(candidates)
      titles: list[str] = []
      owners: list[object] = []
      seasons: list[int] = []
      for anime in candidates:
          for cand in (anime.title, getattr(anime, "title_english", None)):
              if not cand:
                  continue
              titles.append(cand)
              owners.append(anime)
              seasons.append(_parse_season(cand))

      if not titles:
          return None, 0.0

      # Score every candidate in C, keep the top matches, then re-rank the
      # short list with the season penalty (cheap, Python-side).
      top = _rf_process.extract(
          query, titles, scorer=_rf_fuzz.token_set_ratio, limit=25
      )
      best_owner = None
      best_adj = -1.0
      for _title, score, idx in top:
          adj = score
          if seasons[idx] != query_season:
              adj -= SEASON_MISMATCH_PENALTY
          if adj > best_adj:
              best_adj = adj
              best_owner = owners[idx]

      if best_owner is None:
          return None, 0.0
      return best_owner, max(0.0, best_adj)
  ```
  Remove `_strip_season` if it is now unused (grep first: `grep -n "_strip_season\|SEASON_SUFFIX_RE" utils/dub_sources/`); if `animeschedule.py` or anything else imports them, leave them.

- [ ] **Step 4: Run → pass** `python -m pytest tests/test_dub_crunchyroll.py -v` (all pass, including the reversed test).

- [ ] **Step 5: Commit**
  ```bash
  git add utils/dub_sources/crunchyroll.py tests/test_dub_crunchyroll.py
  git commit -m "fix(schedule): match dub feeds to the correct season, not the base row"
  ```

---

## Task 2: Verify the AnimeSchedule source still matches

**Files:** none (verification)

- [ ] **Step 1:** Confirm `animeschedule.py` still imports `best_match` cleanly and its tests pass: `python -m pytest tests/test_dub_animeschedule.py -v`. If it imported `_strip_season` directly and you removed it, restore that symbol or update the import.
- [ ] **Step 2:** No commit unless a fix was needed.

---

## Task 3: Full verification

- [ ] `python -m pytest tests/test_dub_crunchyroll.py tests/test_dub_animeschedule.py tests/test_schedule_week.py -v` then `python -m pytest -q` (all green).
- [ ] Manual sanity (optional): in a Python shell, `best_match("Demon Slayer Season 4", [...])` returns the S4 row when present.

---

## Self-review
- **Spec coverage:** full-title + season-guard matcher (Task 1) ✓; both dub sources covered via shared `best_match` (Task 2) ✓; reversed + expanded tests (Task 1) ✓; no schema/UI (none added) ✓.
- **No placeholders:** `_parse_season`, `SEASON_NUM_RE`, `SEASON_MISMATCH_PENALTY`, and the new `best_match` are given in full; the test step names exact cases and says to reuse the file's candidate-building pattern (read first).
- **Performance:** the O(catalog) scan stays in C via `process.extract`; only the ≤25 top results get Python-side penalty math — no regression vs the prior `extractOne`.
- **Safe failure:** returning the adjusted score means a season-only mismatch is demoted below `MATCH_THRESHOLD` ⇒ no dub written (vs. a wrong-season dub).
- **Out of scope:** episode renumbering/schema, UI, dub-date estimation (D).
