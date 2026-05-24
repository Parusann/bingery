# Schedule revamp — week-anchored day-of-week board

**Date:** 2026-05-24
**Status:** Approved for implementation planning
**Author:** brainstormed with the user; written by the assistant

## 1. Goal

Rebuild `/schedule` into a flagship Bingery page that is reliable, accurate,
and visually arresting. The current page is a flat day-grouped list with a
sub/dub tab and UTC-only times — users have called it unreliable and hard to
read, with the dub section especially underdeveloped.

The redesign anchors on a **Sun→Sat day-of-week board** with a sticky weekly
day strip, an editorial banner per day, and prominent treatment for shows the
user follows. The full visual language is locked in a pre-built handoff bundle
at `Bingery/design_handoff_schedule/` (high-fidelity).

Concretely, after this work:

- A user opens `/schedule` and lands on today's section, with the whole
  current week visible in a sticky strip overhead.
- Each day shows a banner-art collage header followed by a watchlist strip
  (their shows, pinned + gold-accented) and a list of every other release.
- The same page handles sub and dub via a `Sub | Dub | Both` segmented
  control, with synthetic/estimated dub dates clearly labeled.
- Times render in the user's browser timezone with the TZ abbreviation visible.
- URL state (`?week=YYYY-MM-DD&lang=both&mine=0`) makes the view deep-linkable
  and survives reloads.

## 2. Non-goals

- **No new dub data sources.** AnimeSchedule.net's 401 problem is real but
  out of scope for this revamp. We surface synthetic dates with an
  `estimated` marker (per the designer's spec) instead of suppressing them.
- **No backfill of `Anime.popularity`.** That's a cron-sync concern, tracked
  separately.
- **No changes to `/api/anime/<id>/episodes`** or the `NextEpisodeWidget` on
  the anime detail page. The legacy `/api/schedule/upcoming` endpoint also
  stays available — no callers besides the page being rebuilt.
- **No personalized recommendation logic on the schedule page.** It's a
  calendar, not a recommender. The watchlist tie-in is presentational.
- **No push notifications, calendar export, or "remind me" features.** Future
  work.

## 3. Architecture

```
┌─────────── frontend/src/features/schedule/ ─────────────┐
│  SchedulePage  ─ reads URL state via useSearchParams    │
│        │                                                 │
│        ├─ ScheduleHeader (title + FilterPills)           │
│        ├─ DayStrip       (sticky 7-chip week navigator)  │
│        └─ DaySection[]   (one per Sun..Sat)              │
│             ├─ DayBanner (collage / empty variant)       │
│             ├─ EpisodeRow[]  (watchlist, gold-accented)  │
│             ├─ divider                                   │
│             └─ EpisodeRow[]  (everything else)           │
│                                                          │
│  useScheduleWeek(weekStart, lang, mine)  ─ TanStack      │
│        └─ GET /api/schedule/week                         │
└──────────────────────────────────────────────────────────┘

┌─────────── routes/schedule.py ───────────────────────────┐
│  /api/schedule/week         (NEW)                        │
│    params: week, lang, mine                              │
│    response: { week_start, days: [7 × {date, episodes}] }│
│                                                          │
│  /api/schedule/upcoming     (UNCHANGED, kept for legacy) │
│  /api/anime/<id>/episodes   (UNCHANGED)                  │
└──────────────────────────────────────────────────────────┘
```

The page is fully URL-driven. `SchedulePage` reads `?week`, `?lang`, `?mine`
from `useSearchParams`, passes them into `useScheduleWeek`, and renders.
Chevron clicks update the URL, which updates state, which triggers a refetch.

## 4. Backend — new endpoint

### 4.1 Route

```
GET /api/schedule/week?week=YYYY-MM-DD&lang=sub|dub|both&mine=0|1
@jwt_required()
```

- `week`: ISO date of the Sunday that anchors the visible week. Required;
  400 if missing or unparseable.
- `lang`: defaults to `both`; 400 on garbage. Filters which episode kinds
  appear (sub releases, dub releases, or both).
- `mine`: defaults to `0`. When `1`, response only includes episodes whose
  anime is in the requesting user's `WatchlistEntry` set (any status). When
  `0`, all currently airing anime are returned and the `on_watchlist` flag
  tells the client which to highlight.

### 4.2 Response

```json
{
  "week_start": "2026-05-24",
  "days": [
    {
      "date": "2026-05-24",
      "episodes": [
        {
          "id": 12345,
          "anime_id": 678,
          "anime": { "id": 678, "title": "...", "title_english": "...",
                     "image_url": "...", "popularity": 1234 },
          "episode_number": 7,
          "air_time_utc": "2026-05-24T22:30:00Z",
          "type": "sub",
          "estimated": false,
          "on_watchlist": true
        }
      ]
    },
    /* …six more days, Sun..Sat */
  ]
}
```

Field-by-field:

| Field | Notes |
|---|---|
| `week_start` | Same value the client passed, echoed for sanity. |
| `days[].date` | `YYYY-MM-DD` keyed in **UTC**. Client converts to local when rendering individual times — the date bucket itself stays UTC to avoid split-day ambiguity at the boundaries. |
| `episodes[].id` | Episode row primary key. |
| `episodes[].anime` | Inlined `Anime.to_dict()` — title, image, popularity. Saves the client a join. |
| `episodes[].episode_number` | `Episode.episode_number`. |
| `episodes[].air_time_utc` | Full ISO timestamp in UTC. The handoff bundle shows camelCase (`airTimeUtc`) for designer convenience; production TS types keep snake_case to match the rest of `frontend/src/types/models.ts`. |
| `episodes[].type` | `"sub"` or `"dub"`. |
| `episodes[].estimated` | `true` iff `Episode.dub_source == "synthetic_lag_8w"` (or any future synthetic-tagged source). Always `false` for sub rows. |
| `episodes[].on_watchlist` | `true` iff the requesting user has a `WatchlistEntry` for that anime in any status. |

Existing NSFW filtering (`utils.nsfw.maybe_exclude_nsfw`) is applied
unchanged — Hentai always hidden, Ecchi gated behind the existing header.

### 4.3 Implementation notes

- Window math: `start = parse(week)` at 00:00 UTC, `end = start + 7 days`.
  We query `Episode.air_date_sub` / `Episode.air_date_dub` in `[start, end)`
  exactly as the existing `/upcoming` does — same naive-UTC handling.
- The watchlist join is a single `IN` against the user's
  `WatchlistEntry.anime_id` set. For `mine=1`, the inner query filters to
  that set; for `mine=0`, the set is fetched once and used to populate the
  `on_watchlist` flag per row.
- Sort within a day: ascending by `air_time_utc`, then by anime title for
  stability. Same comparator the legacy endpoint uses.

## 5. Frontend — component tree

The handoff bundle at `Bingery/design_handoff_schedule/reference/` is the
canonical source for visuals. Production filenames live under
`frontend/src/features/schedule/`.

| Component | File | Responsibility |
|---|---|---|
| `SchedulePage` | `SchedulePage.tsx` | URL state, layout shell, today auto-scroll on first load |
| `ScheduleHeader` | `ScheduleHeader.tsx` | Page title + filter pill row |
| `FilterPills` | `FilterPills.tsx` | Sub/Dub/Both segmented control + ☆ My shows toggle |
| `DayStrip` | `DayStrip.tsx` | Sticky 7-chip week strip with prev/next-week chevrons |
| `DaySection` | `DaySection.tsx` | One day: banner + watchlist strip + rest |
| `DayBanner` | `DayBanner.tsx` | 232 px collage banner, empty variant, today variant |
| `EpisodeRow` | `EpisodeRow.tsx` | Single episode row; supports `highlighted` and `estimated` variants |
| `Badge` | `Badge.tsx` | Sub (peach) or Dub (sage) badge with dot glow |
| `EstimatedTag` | `EstimatedTag.tsx` | Dashed-border ⓘ "estimated" pill with tooltip |
| `useScheduleWeek` | `hooks/useScheduleWeek.ts` | TanStack Query wrapper around `GET /api/schedule/week` |

**Deleted:** `frontend/src/features/schedule/ScheduleCalendar.tsx`,
`ScheduleEpisodeRow.tsx`. Their tests get rewritten against the new tree.

**Untouched:** `useSchedule` and `useAnimeEpisodes` in `hooks/useSchedule.ts`
— still used by `NextEpisodeWidget`. We *add* `useScheduleWeek` rather than
replace.

## 6. State management

Single source of truth is the URL search params, parsed once per render:

```ts
type ScheduleState = {
  week: string;          // 'YYYY-MM-DD', Sunday of visible week (UTC)
  lang: 'sub' | 'dub' | 'both';
  myShowsOnly: boolean;
};
```

- On mount, if `?week` is missing, default to the Sunday of today's UTC week
  and `navigate({ replace: true })` to canonicalize the URL.
- Filter pill / toggle clicks call `setSearchParams({...})` — the URL change
  drives the query key change, TanStack refetches, layout re-renders.
- Day-chip clicks do *not* change the URL; they smooth-scroll to the matching
  `DaySection` inside the already-loaded week.
- Prev/next-week chevrons shift the `week` param by 7 days.

## 7. Data accuracy treatment

The user's chief complaint was "not reliable, not accurate." We address that
via three concrete moves, none of which require new data sources:

1. **Timezone correctness.** All times render in the user's browser TZ with
   the abbreviation visible (`Intl.DateTimeFormat(undefined, { timeZoneName: 'short' })`).
   No more raw UTC. The day bucket itself stays UTC-keyed (see §4.2) to
   avoid week-boundary ambiguity.
2. **Estimated marker.** Synthetic dub dates (`dub_source = 'synthetic_lag_8w'`)
   render with a dashed-border "estimated" tag and a tooltip explaining
   the source ("Dub date is estimated based on previous release cadence.").
   We stop pretending these are confirmed.
3. **Clean empty days.** When no episodes match, the day still renders with
   an empty banner — the user can see they're looking at an accurate
   calendar, not a broken one. This was a common source of "is it broken
   or is nothing airing today?" confusion.

The AnimeSchedule.net 401 stays unfixed in this revamp — a parallel task can
restore Tier-2 dub freshness once a working API key is available, at which
point those rows transparently lose their `estimated` flag.

## 8. Design tokens

Adopted from `Bingery/design_handoff_schedule/README.md` §Design tokens.
Net additions to `frontend/tailwind.config.js`:

- New color tokens: `peach`, `peach-hi`, `peach-deep`, `sage` (replaces dub
  use of `violet`), `gold`, `gold-bd`, `gold-glow`, `ink`, `ink-2`, `mute`,
  `mute-2`, `line`, `line-2`, `row-bg`, `row-bg-hover`, `row-bd`.
- New font families: `Instrument Serif`, `Geist`, `Geist Mono` (Google
  Fonts). Loaded via a `<link>` in `frontend/index.html`. Existing
  `font.display` / `font.body` / `font.mono` in `src/design/tokens.ts`
  retargeted to these new families.
- Existing `amber` / `violet` tokens remain available for non-schedule
  surfaces (NextEpisodeWidget uses `amber` — untouched).

The schedule page does **not** introduce a parallel design system; it uses
the new tokens via Tailwind utilities like every other page.

## 9. Responsive behavior

Locked in the handoff bundle. Summary:

| Breakpoint | Layout |
|---|---|
| ≥ 1024 px | Full design as mocked. |
| 768 – 1023 px | Header stays horizontal; filter pills don't wrap. |
| ≤ 640 px | Header stacks vertically; filter pills wrap or collapse; day chips shrink to 8.5 px label / 17 px date / 4 px gap; chevrons shrink to 28 px; week meta hides; banner becomes 152 px tall with a single poster (no collage); rows compress to 48 × 64 px poster / 17 px title; row chevron hides. |

## 10. Testing strategy

### Backend
New `tests/test_schedule_week.py`:

- `week` param math: Sunday anchor for an arbitrary mid-week date, Sunday
  passed verbatim, week crosses a month boundary, week crosses a year
  boundary.
- `lang=sub` returns only sub rows; `lang=dub` only dub; `lang=both` both.
- `mine=1` filters to the requesting user's watchlist; `mine=0` includes
  all rows; in both cases `on_watchlist` is populated correctly per row.
- `estimated=true` exactly when `Episode.dub_source` is `synthetic_lag_8w`.
- NSFW Hentai always excluded; Ecchi excluded unless header is set.
- Missing `week`: 400. Garbage `lang`: 400. Garbage `mine`: treated as 0.
- Days with no episodes still appear in the 7-element `days` array with an
  empty `episodes` list.

The existing `tests/test_schedule.py` for `/upcoming` and `/episodes` stays
untouched — those endpoints are unchanged.

### Frontend
New / rewritten tests in `frontend/tests/features/`:

- `DayStrip.test.tsx`: chip states (default, past, selected, today),
  prev/next chevron URL updates, chip click smooth-scrolls to the right
  section.
- `DayBanner.test.tsx`: collage variant renders 3 posters, empty variant
  renders the "No releases" copy, today variant gets the peach border + pulse.
- `EpisodeRow.test.tsx`: highlighted variant (watchlist) shows gold star
  and gold-gradient title; estimated tag renders only on dub rows with
  `estimated=true`; click navigates to `/anime/{anime_id}`.
- `FilterPills.test.tsx`: Sub/Dub/Both segmented control updates the `lang`
  param; My-shows toggle updates `mine`.
- `SchedulePage.test.tsx` (rewritten): unauthenticated state, loading
  skeleton, full-week render, today auto-scrolls on initial load, URL
  state round-trips correctly.

### E2E
`frontend/e2e/demo/06-schedule.spec.ts` updated to drive the new layout
(today chip, banner visible, prev-week navigation, filter toggle).

## 11. Cutover & migration

- No DB migration required. Schema is unchanged; the `estimated` flag is
  derived from the existing `dub_source` column at query time.
- Backend ships the new endpoint behind no flag. Both `/upcoming` and
  `/week` coexist; `/upcoming` remains the source of truth for the
  `NextEpisodeWidget`.
- Frontend swap is atomic from a route perspective — `/schedule` either
  renders the old tree or the new tree depending on which commit is
  deployed. No feature flag; old code is deleted in the same PR.
- The first deploy must include the new Google Fonts link in `index.html`
  to avoid an unstyled flash.

## 12. Open questions / known gaps

- **Dub freshness.** AnimeSchedule.net Tier-2 ingestion is still broken
  (401). Until that's fixed, all dub rows past the most recent
  Crunchyroll-RSS-confirmed episode will carry `estimated=true`. Documented
  here, not blocking.
- **Banner collage on light catalogs.** If a day has 1 or 2 episodes, the
  banner falls back to a 2-poster or 1-poster layout (no smaller). The
  reference HTML shows the 3-poster case; the component handles 1, 2, 3+
  internally. Test coverage included.
- **Past episode rendering.** Episodes whose `air_time_utc < now` still
  render — the calendar is browsable historically. They get no special
  "aired" treatment in v1; that's a future enhancement if requested.
- **My-shows-only empty state.** When `mine=1` and the week has zero
  watchlist episodes, the page shows seven empty banners with "No releases."
  The designer flagged a top-level empty-state as out of scope; we accept
  that — the empty banners are honest signal.
