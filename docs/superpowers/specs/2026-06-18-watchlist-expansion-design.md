# Watchlist Expansion — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/watchlist-expansion`

## Problem

The watchlist is bare-bones. From the product owner:

> Expand the features of watchlist as it is very bare bones right now. We need a
> better filter system for people who have tons of anime saved and a way to
> search anime inside of the watchlist and not just go back to discover. Another
> thing we could add is a different option to view your watchlist similar to how
> you can change how you would like to see files on a computer with preview or a
> smaller preview etc.

Today the page (`frontend/src/features/watchlist/WatchlistPage.tsx`) has exactly
one control — a row of status tabs — and one hardcoded poster grid. There is no
in-list search, no genre/sort/favorites filtering exposed, and no alternate view
modes. A user with hundreds of saved anime silently sees only the first page
(the backend defaults to `per_page=50` and the UI never reads `total`/`pages`).

## Goals

1. **Search inside the watchlist** — filter saved anime by title without leaving
   the page (kills the "bounce back to Discover" problem).
2. **Richer filtering & sorting** — genre filter, favorites-only toggle, and a
   sort control, on top of the existing status tabs.
3. **View modes** — file-explorer-style layout options: Large posters, Compact
   grid, and List rows.

## Non-goals (YAGNI)

- Server-side search/genre/pagination (see "Approach" — deferred unless real
  lists get huge).
- Year / format / score-range filters.
- A "Detailed rows" view mode (the product owner chose 3 modes, not 4).
- Saved filter presets, drag-to-reorder.

## Current state (verified)

- **Endpoint** `GET /api/watchlist` (`routes/watchlist.py`) already supports
  `status`, `sort` (`updated|title|score`), `page`, `per_page` (default 50, max
  100) and returns `{entries, total, page, pages}`. It has **no** text search and
  **no** genre filter. The `sort=score` option sorts by `Anime.api_score`
  (community), not the user's score.
- **Payload already carries everything we need.** `WatchlistEntry.to_dict(include_anime=True)`
  (`models.py:307-332`) serializes `id`, `status`, `episodes_watched`,
  `is_favorite`, `created_at`, `updated_at`, and `anime` via
  `Anime.to_dict(include_community=False)` — which includes `official_genres`
  (`models.py:192`). The watchlist route additionally attaches the user's `score`
  and fan `genres` per entry (`routes/watchlist.py:79-80`).
- **TS type gap:** `WatchEntry` (`frontend/src/types/models.ts:60-71`) declares
  `status`, `episodes_watched`, `is_favorite`, `updated_at`, `score?`, `genres?`
  (fan) and `anime: AnimeSummary` (which already declares `official_genres?`),
  but **omits `created_at`** even though it is serialized.
- **Hook** `useWatchlist(status?)` only forwards `status`; it ignores sort, page,
  and search.

Conclusion: every field needed for client-side search/sort/genre/favorites is
already in the payload. The only missing capability is loading the *whole* list
in one request (the cap is 100).

## Approach

**Client-side filtering over a full-loaded list.**

Load the user's entire watchlist once, then do all search / sort / genre /
favorites / status filtering and view-switching in the browser. This gives
instant, round-trip-free filtering and matches realistic watchlist sizes
(tens to low hundreds; edge cases in the low thousands).

Alternatives considered and rejected:

- **Server-side** (port `routes/anime.py` search/genre/sort + pagination UI):
  scales infinitely but adds backend work, search round-trips, two genre joins
  (official + fan), and pagination that fights "see my whole list" + view modes.
  Over-engineered for current scale.
- **Hybrid** (client-side now, server-side past a threshold): two code paths =
  most complexity. YAGNI.

Mitigation for scale: the filtering/sorting logic lives in a **pure function**
(`lib/watchlistFilter.ts`) decoupled from the component, so it can be lifted to
the server later without a UI rewrite if real data ever demands it.

## Backend changes

`routes/watchlist.py` — add an `all=1` query param to `GET /api/watchlist` that
returns **all** of the user's entries (no pagination), while keeping the existing
per-entry batch loading of ratings and fan genres (already chunked for SQLite's
`IN(...)` limit — `routes/watchlist.py:58`). Paginated behavior is unchanged when
`all` is absent, so nothing else breaks. No serializer change is needed:
`created_at` is already returned.

That is the only backend change.

## Frontend architecture

### Types (`frontend/src/types/models.ts`)
- Add `created_at: string` to `WatchEntry`.
- Add `export type ViewMode = 'large' | 'compact' | 'list'`.
- Add `export type GenreMatchMode = 'any' | 'all'`.

### Data hook (`frontend/src/hooks/useWatchlist.ts`)
- Change the list query to fetch the full list once: `GET /api/watchlist?all=1`,
  query key `['watchlist', 'all']`. Status (and all other filters) are applied
  client-side, so we no longer refetch per status. Mutation hooks (status,
  favorite, episodes) are unchanged except for invalidating `['watchlist','all']`.

### Pure filter module (`frontend/src/lib/watchlistFilter.ts`) — NEW, unit-tested

```ts
interface WatchlistFilterOpts {
  status: WatchStatus | null;
  q: string;
  genres: string[];
  genreMode: GenreMatchMode;   // 'any' | 'all'
  favoritesOnly: boolean;
  sort: 'updated' | 'created' | 'title' | 'score';
}

filterAndSortEntries(entries: WatchEntry[], opts: WatchlistFilterOpts): WatchEntry[]
deriveGenreOptions(entries: WatchEntry[]): string[]   // sorted union of official + fan genre names
deriveStatusCounts(entries: WatchEntry[]): WatchStatusCounts  // all + per-status + favorites
```

Filter semantics:
- **status** — if set, keep entries whose `status` matches.
- **q** — trimmed, lowercased; keep if `anime.title` OR `anime.title_english`
  contains it (case-insensitive).
- **genres** — per entry, build the set of genre names = `anime.official_genres[].name`
  ∪ `entry.genres` (fan). When `genres` is non-empty: `'any'` keeps entries whose
  set intersects the selection; `'all'` keeps entries whose set contains every
  selected genre.
- **favoritesOnly** — keep `is_favorite === true`.
- **sort** — `updated` → `updated_at` desc (default); `created` (Date added) →
  `created_at` desc; `title` → display title (`title_english ?? title`) asc via
  `localeCompare`; `score` (your score) → score desc, nulls last, tiebreak
  `updated_at` desc.

### Page (`frontend/src/features/watchlist/WatchlistPage.tsx`)
- Read/write all controls as URL params (mirrors `DiscoverPage`'s `useSearchParams`):
  `status`, `q`, `sort`, `genres` (comma-separated), `gmode`, `fav`, `view`.
- View mode also persisted to `localStorage('watchlist.view')`. Initial view =
  URL `view` ?? localStorage ?? `'large'`; on change, write both URL and
  localStorage. Filter params are URL-only (not persisted across sessions).
- Loads the full list via `useWatchlist`, computes `deriveStatusCounts` and
  `deriveGenreOptions` (memoized), applies `filterAndSortEntries`, and renders the
  toolbar + status tabs + the active view.
- Empty states: distinguish "your watchlist is empty" (no entries at all) from
  "no anime match your filters" (entries exist but filtered to zero, with a
  clear-filters action). Loading shows skeletons appropriate to the active view.

### Toolbar (`frontend/src/features/watchlist/WatchlistToolbar.tsx`) — NEW
Controls: debounced search input, sort dropdown (Recently updated · Date added ·
Title A–Z · Your score), genre multi-select with the **Match: Any / All** toggle
(only meaningful with 2+ genres selected), favorites-only toggle, and the 3-way
view switcher (Large / Compact / List). Reuses existing pill/button styling from
`FilterBar`/`StatusTabs`. Controls wrap/scroll on narrow widths; touch targets
≥ 40px.

### Cards & rows
- `WatchlistCard.tsx` — add a `variant: 'large' | 'compact'` prop. `large` keeps
  the current layout; `compact` uses a smaller poster, title only (no genre
  badges), in a denser grid.
- `WatchlistRow.tsx` — NEW list-view row: small thumbnail + title + status pill +
  episode progress (`episodes_watched` / `anime.episodes`) + your score badge.
- `StatusTabs.tsx` — accept status counts as a prop (derived from the loaded
  entries) instead of fetching them separately, so counts always match what is
  shown.

### Grid classes per view
- `large` — `grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6` (current).
- `compact` — denser, e.g. `grid-cols-3 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8`.
- `list` — single-column vertical stack of `WatchlistRow`.

## Testing

- **`watchlistFilter` unit tests** (`frontend`): search match (title + English),
  genre `any` vs `all` across official+fan sources, favorites filter, each sort
  order (incl. nulls-last for score), status filter, and `deriveGenreOptions` /
  `deriveStatusCounts`.
- **Backend test** (`tests/test_watchlist.py`): `GET /api/watchlist?all=1` returns
  every entry (more than the default `per_page`) and each entry includes
  `created_at`; paginated behavior unchanged when `all` is absent.

## Rollout / risk

Low risk: one additive backend param, the rest is frontend. No schema or
migration changes. Existing watchlist mutations and the status-tab behavior are
preserved. The change is shippable behind no flag.
