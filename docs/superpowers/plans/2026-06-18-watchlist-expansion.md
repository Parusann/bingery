# Watchlist Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-list search, genre/sort/favorites filtering, and three view modes (large / compact / list) to the watchlist, doing all filtering client-side over a full-loaded list.

**Architecture:** The watchlist payload already carries every field needed (title, official + fan genres, score, is_favorite, created_at). The only backend change is an `all=1` param that returns the whole list unpaginated. The frontend loads it once, then a pure function (`lib/watchlistFilter.ts`) does all search/sort/genre/favorites/status filtering in memory; control state lives in URL params (view mode also in localStorage).

**Tech Stack:** Flask + SQLAlchemy (backend, pytest), React + TypeScript + Vite + Tailwind + react-router + @tanstack/react-query (frontend, vitest).

Spec: `docs/superpowers/specs/2026-06-18-watchlist-expansion-design.md`
Branch: `feat/watchlist-expansion`

---

## File structure

- `routes/watchlist.py` — MODIFY `get_watchlist`: add `all=1` (unpaginated) + chunk the rating/fan-genre `IN(...)` lookups so they're safe for large lists.
- `tests/test_watchlist.py` — ADD a test for `all=1`.
- `frontend/src/types/models.ts` — ADD `created_at` to `WatchEntry`; ADD `ViewMode`, `GenreMatchMode`, `WatchlistSort`.
- `frontend/src/lib/watchlistFilter.ts` — NEW pure filter/sort/derive helpers.
- `frontend/src/lib/watchlistFilter.test.ts` — NEW vitest unit tests.
- `frontend/src/hooks/useWatchlist.ts` — MODIFY `useWatchlist` to load the full list (`?all=1`).
- `frontend/src/features/watchlist/WatchlistCard.tsx` — MODIFY: add `variant: "large" | "compact"`.
- `frontend/src/features/watchlist/WatchlistRow.tsx` — NEW list-view row.
- `frontend/src/features/watchlist/WatchlistToolbar.tsx` — NEW toolbar (search, sort, genre + Any/All, favorites, view switch).
- `frontend/src/features/watchlist/WatchlistPage.tsx` — MODIFY: URL-param state, derive counts/genres, filter, render the active view.

`StatusTabs.tsx` is unchanged: it already accepts a `WatchStats`-shaped `stats` prop and computes the total, so we feed it counts derived from the loaded entries.

---

## Task 1: Backend — `all=1` full-list support

**Files:**
- Modify: `routes/watchlist.py` (the `get_watchlist` function, ~lines 22-88, plus a new helper near the top)
- Test: `tests/test_watchlist.py`

- [ ] **Step 1: Write the failing test**

Add to the end of `tests/test_watchlist.py` (the file already imports `from models import db, Anime, WatchlistEntry` at the top and has a `_anime(title, anilist_id, api_score=8.0)` helper and the `client`/`app`/`auth_headers` fixtures):

```python
def test_all_param_returns_full_list_with_created_at(client, app, auth_headers):
    headers, user = auth_headers
    with app.app_context():
        for i in range(3):
            a = _anime(f"All Param Show {i}", anilist_id=51000 + i)
            db.session.add(
                WatchlistEntry(user_id=user.id, anime_id=a.id, status="watching")
            )
        db.session.commit()

    # Paginated mode still caps results.
    paged = client.get("/api/watchlist?per_page=2", headers=headers).get_json()
    assert len(paged["entries"]) == 2
    assert paged["total"] == 3

    # all=1 returns every entry, unpaginated, each carrying created_at.
    full = client.get("/api/watchlist?all=1", headers=headers).get_json()
    assert len(full["entries"]) == 3
    assert full["total"] == 3
    assert all("created_at" in e for e in full["entries"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_watchlist.py::test_all_param_returns_full_list_with_created_at -v`
Expected: FAIL — `all=1` is ignored today, so the second response is still paginated/identical and the assertion `len(full["entries"]) == 3` may pass by luck only if default per_page≥3; the meaningful failure is that there is no `all` handling yet. (If it passes, the implementation in Step 3 is still required to guarantee unpaginated behavior for >50 entries.)

- [ ] **Step 3: Implement `all=1` + chunked lookups**

In `routes/watchlist.py`, add this helper just below the existing `_parse_episodes` helper near the top of the file:

```python
def _chunks(seq, size=500):
    """Yield successive `size`-length chunks (keeps IN(...) under SQLite's
    ~999 variable limit when returning an unpaginated list)."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
```

Then replace the entire `get_watchlist` function body with:

```python
def get_watchlist():
    """
    GET /api/watchlist?status=watching&sort=updated&page=1&per_page=50
    GET /api/watchlist?all=1   -> every entry, unpaginated (for client-side filtering)
    Get the user's watchlist, optionally filtered by status.
    """
    user_id = int(get_jwt_identity())
    status_filter = request.args.get("status", "").strip()
    sort = request.args.get("sort", "updated")
    return_all = request.args.get("all", "").strip().lower() in ("1", "true", "yes")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    query = db.session.query(WatchlistEntry).filter_by(user_id=user_id)

    if status_filter and status_filter in WATCH_STATUSES:
        query = query.filter_by(status=status_filter)

    if sort == "title":
        query = query.join(Anime).order_by(Anime.title.asc())
    elif sort == "score":
        query = query.join(Anime).order_by(
            Anime.api_score.desc().nullslast(), WatchlistEntry.updated_at.desc()
        )
    else:
        query = query.order_by(WatchlistEntry.updated_at.desc())

    # Eager-load the anime + its genres so building each entry doesn't fire
    # a query per row for them.
    query = query.options(
        selectinload(WatchlistEntry.anime).selectinload(Anime.official_genres)
    )

    if return_all:
        items = query.all()
        total = len(items)
        out_page, out_pages = 1, 1
    else:
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        items = paginated.items
        total = paginated.total
        out_page, out_pages = paginated.page, paginated.pages

    # Batch the per-entry rating + fan-genre lookups that to_dict(include_anime)
    # would otherwise issue one-by-one (the N+1). Chunk the IN(...) so an
    # unpaginated list stays under SQLite's variable limit.
    anime_ids = [e.anime_id for e in items]
    score_by_anime = {}
    votes_by_anime = {}
    for chunk in _chunks(anime_ids):
        score_by_anime.update(
            dict(
                db.session.query(Rating.anime_id, Rating.score).filter(
                    Rating.user_id == user_id, Rating.anime_id.in_(chunk)
                )
            )
        )
        for aid, tag in db.session.query(
            FanGenreVote.anime_id, FanGenreVote.genre_tag
        ).filter(
            FanGenreVote.user_id == user_id, FanGenreVote.anime_id.in_(chunk)
        ):
            votes_by_anime.setdefault(aid, []).append(tag)

    entries = []
    for e in items:
        d = e.to_dict(include_anime=False)
        d["anime"] = e.anime.to_dict(include_community=False)
        d["score"] = score_by_anime.get(e.anime_id)
        d["genres"] = votes_by_anime.get(e.anime_id, [])
        entries.append(d)

    return jsonify({
        "entries": entries,
        "total": total,
        "page": out_page,
        "pages": out_pages,
    }), 200
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_watchlist.py -v`
Expected: PASS (the new test and all existing watchlist tests, including `test_list_watchlist_does_not_n_plus_one` and `test_sort_by_score_orders_by_anime_score`).

- [ ] **Step 5: Commit**

```bash
git add routes/watchlist.py tests/test_watchlist.py
git commit -m "feat(watchlist): support all=1 to return the full list unpaginated"
```

---

## Task 2: Frontend types + pure filter module

**Files:**
- Modify: `frontend/src/types/models.ts`
- Create: `frontend/src/lib/watchlistFilter.ts`
- Test: `frontend/src/lib/watchlistFilter.test.ts`

- [ ] **Step 1: Add the types**

In `frontend/src/types/models.ts`, add `created_at: string;` to the `WatchEntry` interface (after `updated_at: string;`):

```ts
export interface WatchEntry {
  id: number;
  anime: AnimeSummary;
  status: WatchStatus;
  episodes_watched: number;
  is_favorite: boolean;
  updated_at: string;
  created_at: string;
  /** The score (1-10) this user gave the anime, or null if unrated. */
  score?: number | null;
  /** Fan-genre tags this user assigned to the anime. */
  genres?: string[];
}
```

Then add these type aliases anywhere in the file (e.g. just below `WatchStatus`):

```ts
export type ViewMode = "large" | "compact" | "list";
export type GenreMatchMode = "any" | "all";
export type WatchlistSort = "updated" | "created" | "title" | "score";
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/lib/watchlistFilter.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import {
  filterAndSortEntries,
  deriveGenreOptions,
  deriveStatusCounts,
} from "./watchlistFilter";
import type { WatchEntry, WatchStatus } from "@/types/models";

function entry(o: {
  id: number;
  title?: string;
  titleEn?: string | null;
  status?: WatchStatus;
  favorite?: boolean;
  score?: number | null;
  created?: string;
  updated?: string;
  official?: string[];
  fan?: string[];
}): WatchEntry {
  return {
    id: o.id,
    status: o.status ?? "watching",
    episodes_watched: 0,
    is_favorite: o.favorite ?? false,
    created_at: o.created ?? "2024-01-01T00:00:00",
    updated_at: o.updated ?? "2024-01-01T00:00:00",
    score: o.score ?? null,
    genres: o.fan ?? [],
    anime: {
      id: o.id,
      anilist_id: null,
      title: o.title ?? `Show ${o.id}`,
      title_english: o.titleEn ?? null,
      title_japanese: null,
      description: null,
      image_url: null,
      banner_url: null,
      episodes: null,
      season: null,
      year: null,
      format: null,
      status: null,
      api_score: null,
      community_score: null,
      rating_count: null,
      official_genres: (o.official ?? []).map((name) => ({ name })),
    },
  };
}

const base = {
  status: null as WatchStatus | null,
  q: "",
  genres: [] as string[],
  genreMode: "any" as const,
  favoritesOnly: false,
  sort: "updated" as const,
};

describe("filterAndSortEntries", () => {
  it("searches title and English title, case-insensitively", () => {
    const list = [
      entry({ id: 1, title: "Dragon Ball" }),
      entry({ id: 2, title: "Naruto", titleEn: "Ninja Tale" }),
      entry({ id: 3, title: "Bleach" }),
    ];
    expect(filterAndSortEntries(list, { ...base, q: "dragon" }).map((e) => e.id)).toEqual([1]);
    expect(filterAndSortEntries(list, { ...base, q: "ninja" }).map((e) => e.id)).toEqual([2]);
  });

  it("matches ANY selected genre across official + fan genres", () => {
    const list = [
      entry({ id: 1, official: ["Action"] }),
      entry({ id: 2, fan: ["Comedy"] }),
      entry({ id: 3, official: ["Drama"] }),
    ];
    const out = filterAndSortEntries(list, { ...base, genres: ["Action", "Comedy"], genreMode: "any" });
    expect(out.map((e) => e.id).sort()).toEqual([1, 2]);
  });

  it("matches ALL selected genres when genreMode is all", () => {
    const list = [
      entry({ id: 1, official: ["Action"], fan: ["Comedy"] }),
      entry({ id: 2, official: ["Action"] }),
    ];
    const out = filterAndSortEntries(list, { ...base, genres: ["Action", "Comedy"], genreMode: "all" });
    expect(out.map((e) => e.id)).toEqual([1]);
  });

  it("filters favorites only", () => {
    const list = [entry({ id: 1, favorite: true }), entry({ id: 2, favorite: false })];
    expect(filterAndSortEntries(list, { ...base, favoritesOnly: true }).map((e) => e.id)).toEqual([1]);
  });

  it("sorts by title A-Z using the display title", () => {
    const list = [entry({ id: 1, title: "Zeta" }), entry({ id: 2, title: "Alpha" })];
    expect(filterAndSortEntries(list, { ...base, sort: "title" }).map((e) => e.id)).toEqual([2, 1]);
  });

  it("sorts by your score descending, nulls last", () => {
    const list = [
      entry({ id: 1, score: 5 }),
      entry({ id: 2, score: null }),
      entry({ id: 3, score: 9 }),
    ];
    expect(filterAndSortEntries(list, { ...base, sort: "score" }).map((e) => e.id)).toEqual([3, 1, 2]);
  });

  it("sorts by date added descending", () => {
    const list = [
      entry({ id: 1, created: "2024-01-01T00:00:00" }),
      entry({ id: 2, created: "2024-05-01T00:00:00" }),
    ];
    expect(filterAndSortEntries(list, { ...base, sort: "created" }).map((e) => e.id)).toEqual([2, 1]);
  });

  it("filters by status", () => {
    const list = [
      entry({ id: 1, status: "completed" }),
      entry({ id: 2, status: "watching" }),
    ];
    expect(filterAndSortEntries(list, { ...base, status: "completed" }).map((e) => e.id)).toEqual([1]);
  });
});

describe("deriveGenreOptions", () => {
  it("returns the sorted unique union of official and fan genres", () => {
    const list = [
      entry({ id: 1, official: ["Action", "Drama"], fan: ["Comedy"] }),
      entry({ id: 2, official: ["Action"], fan: ["Isekai"] }),
    ];
    expect(deriveGenreOptions(list)).toEqual(["Action", "Comedy", "Drama", "Isekai"]);
  });
});

describe("deriveStatusCounts", () => {
  it("counts per status and favorites", () => {
    const list = [
      entry({ id: 1, status: "watching", favorite: true }),
      entry({ id: 2, status: "watching" }),
      entry({ id: 3, status: "completed", favorite: true }),
    ];
    const c = deriveStatusCounts(list);
    expect(c.watching).toBe(2);
    expect(c.completed).toBe(1);
    expect(c.favorites).toBe(2);
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run (from `frontend/`): `npx vitest run src/lib/watchlistFilter.test.ts`
Expected: FAIL — `Cannot find module "./watchlistFilter"`.

- [ ] **Step 4: Implement the module**

Create `frontend/src/lib/watchlistFilter.ts`:

```ts
import type {
  WatchEntry,
  WatchStatus,
  WatchStats,
  GenreMatchMode,
  WatchlistSort,
} from "@/types/models";

export interface WatchlistFilterOpts {
  status: WatchStatus | null;
  q: string;
  genres: string[];
  genreMode: GenreMatchMode;
  favoritesOnly: boolean;
  sort: WatchlistSort;
}

/** Every genre name on an entry: the anime's official genres + the user's fan tags. */
function entryGenreNames(entry: WatchEntry): string[] {
  const official = (entry.anime.official_genres ?? []).map((g) => g.name);
  const fan = entry.genres ?? [];
  return [...official, ...fan];
}

export function filterAndSortEntries(
  entries: WatchEntry[],
  opts: WatchlistFilterOpts
): WatchEntry[] {
  const q = opts.q.trim().toLowerCase();
  const wanted = opts.genres.map((g) => g.toLowerCase());

  const filtered = entries.filter((e) => {
    if (opts.status && e.status !== opts.status) return false;
    if (opts.favoritesOnly && !e.is_favorite) return false;

    if (q) {
      const t = e.anime.title?.toLowerCase() ?? "";
      const te = e.anime.title_english?.toLowerCase() ?? "";
      if (!t.includes(q) && !te.includes(q)) return false;
    }

    if (wanted.length) {
      const have = new Set(entryGenreNames(e).map((g) => g.toLowerCase()));
      if (opts.genreMode === "all") {
        if (!wanted.every((g) => have.has(g))) return false;
      } else if (!wanted.some((g) => have.has(g))) {
        return false;
      }
    }
    return true;
  });

  const sorted = [...filtered];
  sorted.sort((a, b) => {
    switch (opts.sort) {
      case "title": {
        const ta = (a.anime.title_english ?? a.anime.title ?? "").toLowerCase();
        const tb = (b.anime.title_english ?? b.anime.title ?? "").toLowerCase();
        return ta.localeCompare(tb);
      }
      case "created":
        return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      case "score": {
        const sa = a.score ?? -1;
        const sb = b.score ?? -1;
        if (sb !== sa) return sb - sa;
        return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");
      }
      case "updated":
      default:
        return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");
    }
  });
  return sorted;
}

export function deriveGenreOptions(entries: WatchEntry[]): string[] {
  const set = new Set<string>();
  for (const e of entries) for (const g of entryGenreNames(e)) set.add(g);
  return [...set].sort((a, b) => a.localeCompare(b));
}

export function deriveStatusCounts(entries: WatchEntry[]): WatchStats {
  const counts: WatchStats = {
    watching: 0,
    completed: 0,
    plan_to_watch: 0,
    on_hold: 0,
    dropped: 0,
    favorites: 0,
  };
  for (const e of entries) {
    if (e.status in counts) (counts as Record<string, number>)[e.status] += 1;
    if (e.is_favorite) counts.favorites += 1;
  }
  return counts;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run (from `frontend/`): `npx vitest run src/lib/watchlistFilter.test.ts`
Expected: PASS (all assertions in the three describe blocks).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/lib/watchlistFilter.ts frontend/src/lib/watchlistFilter.test.ts
git commit -m "feat(watchlist): add view-mode/sort types and pure filter module with tests"
```

---

## Task 3: Load the full watchlist in the data hook

**Files:**
- Modify: `frontend/src/hooks/useWatchlist.ts`

- [ ] **Step 1: Change `useWatchlist` to fetch the full list**

Replace the `useWatchlist` function (lines 6-14) with:

```ts
export function useWatchlist() {
  const user = useAuth((s) => s.user);
  return useQuery({
    queryKey: ["watchlist", "all"],
    // Load the entire list once; all filtering/sorting happens client-side.
    queryFn: () => api.getWatchlist("?all=1"),
    // Signed-out visitors have no watchlist — don't fire guaranteed 401s.
    enabled: !!user,
  });
}
```

The `WatchStatus` import is still used by the mutation hooks below, so leave the imports unchanged. `invalidateFor` already invalidates the `["watchlist"]` key prefix, which covers `["watchlist","all"]`.

- [ ] **Step 2: Verify it typechecks**

Run (from `frontend/`): `npx tsc -b`
Expected: a type error in `WatchlistPage.tsx` at the `useWatchlist(status ?? undefined)` call (it now takes no argument). That is expected and fixed in Task 7. No other file calls `useWatchlist()`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useWatchlist.ts
git commit -m "feat(watchlist): load the full list client-side via all=1"
```

---

## Task 4: WatchlistCard view variant

**Files:**
- Modify: `frontend/src/features/watchlist/WatchlistCard.tsx`

- [ ] **Step 1: Add the `variant` prop**

Replace the whole file with:

```tsx
import { Link } from "react-router-dom";
import type { WatchEntry } from "@/types/models";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

/**
 * Watchlist tile: the anime poster plus the two things you personally gave it —
 * your rating (score out of 10) and the fan-genres you assigned. Links through
 * to the detail page. `compact` shrinks padding and hides the genre row for a
 * denser grid.
 */
export function WatchlistCard({
  entry,
  variant = "large",
}: {
  entry: WatchEntry;
  variant?: "large" | "compact";
}) {
  const a = entry.anime;
  const genres = entry.genres ?? [];
  const compact = variant === "compact";
  return (
    <Link
      to={`/anime/${a.id}`}
      className="group block overflow-hidden rounded-lg border border-border bg-surface transition-colors hover:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50"
    >
      <div className="relative aspect-[2/3] overflow-hidden bg-black/40">
        {a.image_url ? (
          <img
            src={a.image_url}
            alt={a.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-text-dim">
            No image
          </div>
        )}
        {entry.score != null ? (
          <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md bg-black/70 px-2 py-0.5 font-mono text-xs text-amber backdrop-blur-md">
            ★ {entry.score}/10
          </span>
        ) : (
          <span className="absolute right-2 top-2 rounded-md bg-black/60 px-2 py-0.5 font-mono text-[10px] text-text-dim backdrop-blur-md">
            unrated
          </span>
        )}
      </div>
      <div className={compact ? "p-2" : "p-3"}>
        <h3
          className={
            compact
              ? "line-clamp-2 text-xs font-semibold"
              : "mb-1.5 line-clamp-2 text-sm font-semibold"
          }
        >
          {a.title_english ?? a.title}
        </h3>
        {!compact ? (
          genres.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {genres.slice(0, 6).map((g) => (
                <Badge key={g} color={genreColor(g)}>
                  {g}
                </Badge>
              ))}
              {genres.length > 6 ? (
                <span className="self-center text-[10px] text-text-dim">
                  +{genres.length - 6}
                </span>
              ) : null}
            </div>
          ) : (
            <p className="text-[11px] text-text-dim">No genres assigned yet</p>
          )
        ) : null}
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Verify it typechecks**

Run (from `frontend/`): `npx tsc -b`
Expected: same single pre-existing error in `WatchlistPage.tsx` (fixed in Task 7); no new errors from this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/watchlist/WatchlistCard.tsx
git commit -m "feat(watchlist): add compact variant to WatchlistCard"
```

---

## Task 5: WatchlistRow (list view)

**Files:**
- Create: `frontend/src/features/watchlist/WatchlistRow.tsx`

- [ ] **Step 1: Create the row component**

Create `frontend/src/features/watchlist/WatchlistRow.tsx`:

```tsx
import { Link } from "react-router-dom";
import type { WatchEntry } from "@/types/models";
import { STATUSES } from "./StatusTabs";

/**
 * List-view row: small thumbnail, title, status, episode progress, and your
 * score. Denser than the poster card; used by the "List" view mode.
 */
export function WatchlistRow({ entry }: { entry: WatchEntry }) {
  const a = entry.anime;
  const statusMeta = STATUSES.find((s) => s.key === entry.status);
  const total = a.episodes ?? null;
  return (
    <Link
      to={`/anime/${a.id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50"
    >
      <div className="relative aspect-[2/3] w-10 shrink-0 overflow-hidden rounded bg-black/40">
        {a.image_url ? (
          <img
            src={a.image_url}
            alt={a.title}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-sm font-semibold">
          {a.title_english ?? a.title}
        </h3>
        <div className="mt-0.5 flex items-center gap-2 text-xs">
          {statusMeta ? (
            <span style={{ color: statusMeta.color }}>{statusMeta.label}</span>
          ) : null}
          <span className="text-text-dim">
            ep {entry.episodes_watched}
            {total != null ? ` / ${total}` : ""}
          </span>
        </div>
      </div>
      {entry.score != null ? (
        <span className="shrink-0 font-mono text-xs text-amber">
          ★ {entry.score}
        </span>
      ) : (
        <span className="shrink-0 text-[10px] text-text-dim">unrated</span>
      )}
    </Link>
  );
}
```

- [ ] **Step 2: Verify it typechecks**

Run (from `frontend/`): `npx tsc -b`
Expected: same single pre-existing error in `WatchlistPage.tsx` (fixed in Task 7); no new errors from this file. (`STATUSES` is already exported from `StatusTabs.tsx`.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/watchlist/WatchlistRow.tsx
git commit -m "feat(watchlist): add list-view row component"
```

---

## Task 6: WatchlistToolbar

**Files:**
- Create: `frontend/src/features/watchlist/WatchlistToolbar.tsx`

- [ ] **Step 1: Create the toolbar**

Create `frontend/src/features/watchlist/WatchlistToolbar.tsx`:

```tsx
import type { WatchlistSort, GenreMatchMode, ViewMode } from "@/types/models";
import { cn } from "@/lib/cn";

export type ToolbarPatch = Partial<{
  q: string;
  sort: WatchlistSort;
  genres: string[];
  genreMode: GenreMatchMode;
  favoritesOnly: boolean;
  view: ViewMode;
}>;

const SORTS: Array<{ key: WatchlistSort; label: string }> = [
  { key: "updated", label: "Recently updated" },
  { key: "created", label: "Date added" },
  { key: "title", label: "Title A–Z" },
  { key: "score", label: "Your score" },
];

const VIEWS: Array<{ key: ViewMode; label: string }> = [
  { key: "large", label: "Large" },
  { key: "compact", label: "Compact" },
  { key: "list", label: "List" },
];

interface Props {
  q: string;
  sort: WatchlistSort;
  genres: string[];
  genreOptions: string[];
  genreMode: GenreMatchMode;
  favoritesOnly: boolean;
  view: ViewMode;
  onChange: (patch: ToolbarPatch) => void;
}

export function WatchlistToolbar({
  q,
  sort,
  genres,
  genreOptions,
  genreMode,
  favoritesOnly,
  view,
  onChange,
}: Props) {
  return (
    <div className="mb-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => onChange({ q: e.target.value })}
          placeholder="Search your watchlist"
          aria-label="Search your watchlist"
          className="min-w-[180px] flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-border-strong"
        />
        <select
          value={sort}
          onChange={(e) => onChange({ sort: e.target.value as WatchlistSort })}
          aria-label="Sort"
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm"
        >
          {SORTS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => onChange({ favoritesOnly: !favoritesOnly })}
          aria-pressed={favoritesOnly}
          className={cn(
            "rounded-lg border px-3 py-2 text-sm",
            favoritesOnly
              ? "border-amber bg-amber/10 text-amber"
              : "border-border text-text-muted hover:border-border-strong"
          )}
        >
          ★ Favorites
        </button>
        <div
          role="group"
          aria-label="View mode"
          className="inline-flex overflow-hidden rounded-lg border border-border"
        >
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => onChange({ view: v.key })}
              aria-pressed={view === v.key}
              className={cn(
                "px-3 py-2 text-sm",
                view === v.key ? "bg-amber text-bg" : "text-text-muted hover:text-text"
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {genreOptions.length > 0 ? (
        <div className="flex items-center gap-2">
          <div className="flex flex-1 gap-2 overflow-x-auto pb-1">
            {genreOptions.map((g) => {
              const on = genres.includes(g);
              return (
                <button
                  key={g}
                  type="button"
                  onClick={() =>
                    onChange({
                      genres: on ? genres.filter((x) => x !== g) : [...genres, g],
                    })
                  }
                  aria-pressed={on}
                  className={cn(
                    "shrink-0 rounded-full border px-3 py-1 text-xs",
                    on
                      ? "border-amber bg-amber/10 text-amber"
                      : "border-border text-text-muted hover:border-border-strong"
                  )}
                >
                  {g}
                </button>
              );
            })}
          </div>
          {genres.length > 1 ? (
            <button
              type="button"
              onClick={() =>
                onChange({ genreMode: genreMode === "any" ? "all" : "any" })
              }
              title="Match anime that have any vs all of the selected genres"
              className="shrink-0 rounded-lg border border-border px-3 py-1 text-xs text-text-muted hover:border-border-strong"
            >
              Match: {genreMode === "any" ? "Any" : "All"}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Verify it typechecks**

Run (from `frontend/`): `npx tsc -b`
Expected: same single pre-existing error in `WatchlistPage.tsx` (fixed in Task 7); no new errors from this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/watchlist/WatchlistToolbar.tsx
git commit -m "feat(watchlist): add toolbar (search, sort, genre + any/all, favorites, view)"
```

---

## Task 7: Wire up WatchlistPage

**Files:**
- Modify: `frontend/src/features/watchlist/WatchlistPage.tsx`

- [ ] **Step 1: Replace the page**

Replace the whole file with:

```tsx
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type {
  WatchStatus,
  ViewMode,
  GenreMatchMode,
  WatchlistSort,
} from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { StatusTabs } from "./StatusTabs";
import { WatchlistCard } from "./WatchlistCard";
import { WatchlistRow } from "./WatchlistRow";
import { WatchlistToolbar, type ToolbarPatch } from "./WatchlistToolbar";
import { useAuth } from "@/stores/auth";
import { useWatchlist } from "@/hooks/useWatchlist";
import {
  filterAndSortEntries,
  deriveGenreOptions,
  deriveStatusCounts,
} from "@/lib/watchlistFilter";

const VIEW_GRID: Record<ViewMode, string> = {
  large: "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4",
  compact: "grid grid-cols-3 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-3",
  list: "flex flex-col gap-2",
};

type FilterPatch = ToolbarPatch & { status?: WatchStatus | null };

export function WatchlistPage() {
  const user = useAuth((s) => s.user);
  const wl = useWatchlist();
  const [params, setParams] = useSearchParams();

  const status = (params.get("status") as WatchStatus) || null;
  const q = params.get("q") ?? "";
  const sort = (params.get("sort") as WatchlistSort) || "updated";
  const genres = params.get("genres")
    ? params.get("genres")!.split(",").filter(Boolean)
    : [];
  const genreMode: GenreMatchMode = params.get("gmode") === "all" ? "all" : "any";
  const favoritesOnly = params.get("fav") === "1";
  const view: ViewMode =
    (params.get("view") as ViewMode) ||
    ((typeof localStorage !== "undefined" &&
      (localStorage.getItem("watchlist.view") as ViewMode)) ||
      "large");

  function update(patch: FilterPatch) {
    const next = new URLSearchParams(params);
    const apply = (key: string, val: string | null) => {
      if (val == null || val === "") next.delete(key);
      else next.set(key, val);
    };
    if ("q" in patch) apply("q", patch.q ?? null);
    if ("sort" in patch) apply("sort", patch.sort ?? null);
    if ("genres" in patch)
      apply("genres", patch.genres && patch.genres.length ? patch.genres.join(",") : null);
    if ("genreMode" in patch) apply("gmode", patch.genreMode === "all" ? "all" : null);
    if ("favoritesOnly" in patch) apply("fav", patch.favoritesOnly ? "1" : null);
    if ("status" in patch) apply("status", patch.status ?? null);
    if ("view" in patch && patch.view) {
      apply("view", patch.view);
      if (typeof localStorage !== "undefined")
        localStorage.setItem("watchlist.view", patch.view);
    }
    setParams(next, { replace: true });
  }

  const allEntries = wl.data?.entries ?? [];
  const statusCounts = useMemo(() => deriveStatusCounts(allEntries), [allEntries]);
  const genreOptions = useMemo(() => deriveGenreOptions(allEntries), [allEntries]);
  const visible = useMemo(
    () =>
      filterAndSortEntries(allEntries, {
        status,
        q,
        genres,
        genreMode,
        favoritesOnly,
        sort,
      }),
    [allEntries, status, q, genres, genreMode, favoritesOnly, sort]
  );

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in to track</h1>
        <p className="text-text-muted">
          Your watching, completed, and plan-to-watch list lives here.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-5">Your watchlist</h1>
      <WatchlistToolbar
        q={q}
        sort={sort}
        genres={genres}
        genreOptions={genreOptions}
        genreMode={genreMode}
        favoritesOnly={favoritesOnly}
        view={view}
        onChange={update}
      />
      <StatusTabs
        stats={statusCounts}
        value={status}
        onChange={(s) => update({ status: s })}
      />
      {wl.isLoading ? (
        <div className={VIEW_GRID[view]}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="aspect-[2/3]" rounded="lg" />
              <Skeleton className="h-3 mt-2 w-3/4" />
            </div>
          ))}
        </div>
      ) : allEntries.length === 0 ? (
        <div className="py-24 text-center text-text-muted">
          Nothing here yet — add anime from the discover page.
        </div>
      ) : visible.length === 0 ? (
        <div className="py-24 text-center text-text-muted">
          No anime match your filters.{" "}
          <button
            type="button"
            className="text-amber underline"
            onClick={() => setParams(new URLSearchParams(), { replace: true })}
          >
            Clear filters
          </button>
        </div>
      ) : view === "list" ? (
        <div className={VIEW_GRID.list}>
          {visible.map((e) => (
            <WatchlistRow key={e.id} entry={e} />
          ))}
        </div>
      ) : (
        <div className={VIEW_GRID[view]}>
          {visible.map((e) => (
            <WatchlistCard
              key={e.id}
              entry={e}
              variant={view === "compact" ? "compact" : "large"}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the whole frontend typechecks and builds**

Run (from `frontend/`): `npm run build`
Expected: PASS (`tsc -b` clean, `vite build` succeeds). The previously-expected `useWatchlist` argument error is now gone.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/watchlist/WatchlistPage.tsx
git commit -m "feat(watchlist): wire search, filters, sort, and view modes into the page"
```

---

## Task 8: Full verification

**Files:** none (verification + manual smoke)

- [ ] **Step 1: Backend test suite (watchlist)**

Run: `python -m pytest tests/test_watchlist.py -v`
Expected: all PASS.

- [ ] **Step 2: Frontend unit tests + build**

Run (from `frontend/`): `npx vitest run` then `npm run build`
Expected: filter tests PASS; build succeeds.

- [ ] **Step 3: Manual smoke (dev server)**

Run the app (backend + `cd frontend && npm run dev`), sign in as a user with several saved anime, open the watchlist, and verify:
- typing in the search box filters the list as you type;
- the sort dropdown reorders (esp. "Your score" and "Date added");
- selecting genres filters; selecting 2+ shows the Match: Any/All toggle and it changes results;
- the favorites toggle filters;
- switching Large / Compact / List re-renders correctly;
- the chosen view persists after a refresh (localStorage) and filters survive refresh (URL params);
- a filter combination that matches nothing shows the "No anime match your filters" empty state with a working Clear filters button.

- [ ] **Step 4: Final confirmation**

No commit needed if Steps 1-3 are green and nothing changed. If a smoke issue required a fix, commit it with a descriptive message.

---

## Self-review

- **Spec coverage:** in-list search (Task 2 filter + Task 6 toolbar + Task 7 wiring) ✓; sort incl. your-score and date-added (Task 2 + 6 + 7) ✓; genre filter on official **and** fan with Any/All toggle (Task 2 + 6 + 7) ✓; favorites-only (Task 2 + 6 + 7) ✓; three view modes large/compact/list (Tasks 4, 5, 7) ✓; full-list load + `created_at` (Tasks 1, 2, 3) ✓; URL-param + localStorage persistence (Task 7) ✓; tests for the pure function + backend `all=1` (Tasks 1, 2) ✓; empty/loading states (Task 7) ✓.
- **No placeholders:** every code step contains complete code; every run step has an exact command + expected result.
- **Type consistency:** `filterAndSortEntries` / `deriveGenreOptions` / `deriveStatusCounts` signatures match between Task 2's definition and Task 7's usage; `ToolbarPatch` is exported in Task 6 and imported in Task 7; `variant` prop values ("large"/"compact") match between Task 4 and Task 7; `ViewMode`/`GenreMatchMode`/`WatchlistSort` defined in Task 2 and used consistently.
- **Out of scope (per spec):** server-side pagination, year/format filters, detailed-rows view, saved presets, drag-reorder — none added.
