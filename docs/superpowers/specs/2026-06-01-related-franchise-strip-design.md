# Related franchise strip — "Watch the rest in order!"

**Date:** 2026-06-01
**Status:** Approved (design); pending spec review
**Area:** Anime detail page (frontend + backend)

## Summary

On the anime detail page, add a section that shows every entry in the same
franchise — seasons, movies, OVAs, specials — as a wrapping strip of poster
cards ordered by release date, with the currently-viewed title highlighted.
The section sits directly under the **Community fan genres** section.

Relations are **not** stored in our database, so the data is pulled live from
AniList at view time and rendered on our own page. Entries that exist in our
catalog link to their Bingery detail page; entries we don't have are shown as
non-clickable cards using AniList's data.

## Goal & user-facing behavior

- Clicking into an anime shows a "Watch the rest in order!" strip beneath the
  fan-genre votes.
- The strip lists the whole franchise (not just immediate neighbors) in
  ascending release-date order.
- Each card shows: poster thumbnail, title, a format badge (TV / Movie / OVA /
  Special / ONA / …), and the release date/year.
- The current anime is visually highlighted ("Current" tag + accent ring) and
  is not a link.
- Cards overflow onto new lines (responsive wrapping grid) — never a single
  horizontal scroll row — so layout and card size stay consistent.
- Standalone anime (no franchise relations) → section is hidden.

## Decisions (locked during brainstorming)

1. **Scope:** same-franchise chain only — prequels, sequels, side stories,
   parent stories, and alternative versions. Excludes the source manga/novel
   (ADAPTATION), spin-offs, recaps/summaries, and character links.
2. **Catalog gaps:** show **all** franchise entries. Pull missing ones from
   AniList and render them on our page; only catalog entries are clickable.
3. **Layout:** wrapping horizontal poster strip (not a vertical timeline, not a
   single scroll row). Card = poster + title + format + release date; current
   anime highlighted.
4. **Non-catalog click (v1):** non-clickable card. "Import on click" is a
   future enhancement, out of scope here.

## Data source & rationale

The `Anime` table stores no inter-title relations, no media `format`, and only
`year` + airing `season` (no precise date). AniList is the upstream source and
the codebase already does request-time AniList fetches
(`routes/anilist.py` → `AniListClient.get_anime`). So we surface relations live
at view time rather than migrating the schema and re-syncing 12k+ titles.

- **Chosen:** live AniList fetch at view time, cached. No schema change, no
  re-sync, always fresh, reuses the existing AniList client and the proven
  `/anime/<id>/similar` → `useSimilar` → strip pattern.
- **Rejected:** persist relations (new `AnimeRelation` table + `format` +
  `start_date` columns, populate during sync). Faster reads but a migration
  plus a full catalog re-sync for one UI section — disproportionate. Revisit if
  relations are later needed across many features (filtering, sorting catalog
  by date, offline use).

**Cost & mitigation:** a detail view triggers AniList calls on cache-miss.
Mitigated by a per-title in-process TTL cache (the app runs a single gunicorn
worker, so the cache is effectively global) and bounded traversal caps. AniList
relations change rarely.

## Backend design

### Endpoint

`GET /api/anime/<int:anime_id>/related` (added to `routes/anime.py`, no auth
required — pure catalog data, consistent with the existing detail/similar
routes).

Response:

```json
{
  "related": [
    {
      "anilist_id": 16498,
      "id": 42,                    // local Bingery anime id, or null if not in catalog
      "title": "Shingeki no Kyojin",
      "format": "TV",              // display label, or null
      "release_date": "2013-04-07",// ISO date if full date known, else null
      "year": 2013,                // fallback ordering/display, or null
      "image_url": "https://...",  // local poster if in catalog, else AniList cover
      "is_current": false
    }
  ]
}
```

Behavior:

1. Load the `Anime` by internal id (404 if missing, matching existing routes).
2. If `anime.anilist_id` is `None` → return `{ "related": [] }` (can't fetch).
3. Assemble the franchise (traversal below), map to catalog, inject current
   title, sort by release date, map format labels.
4. If only the current title remains (no franchise) → still return it; the
   frontend hides a single-entry strip.
5. On any AniList error, catch, log, and return `{ "related": [] }` with 200 so
   the section simply hides — the detail page is never broken by an upstream
   failure.

### AniList client — `get_anime_relations(anilist_id)`

New method on `AniListClient` (`utils/anilist.py`) using a **dedicated**
`RELATIONS_QUERY` — deliberately **not** the shared `...AnimeFields` fragment,
so the large catalog-sync payload is unchanged.

```graphql
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english }
    format
    seasonYear
    startDate { year month day }
    coverImage { large medium }
    relations {
      edges {
        relationType
        node {
          id
          type
          title { romaji english }
          format
          seasonYear
          startDate { year month day }
          coverImage { large medium }
        }
      }
    }
  }
}
```

Returns a normalized dict:

```python
{
  "self":  { "anilist_id", "title", "format", "year", "release_date", "image_url" },
  "edges": [
    { "relation_type": "SEQUEL",
      "node": { "anilist_id", "title", "format", "year", "release_date", "image_url", "type" } },
    ...
  ],
}
```

`self` is always `type == ANIME` (the query constrains it). Edge nodes carry
`type` because relations can point at non-anime media (manga/novel) that the
traversal filters out.

Wrapped in a module-level TTL cache keyed by `anilist_id` (TTL ~24h), so each
title is fetched at most once per day across all detail views.

### Franchise assembly (bounded traversal)

AniList `relations` are one-hop only, so a single fetch misses distant entries.
A bounded breadth-first traversal across **franchise edges** gathers the whole
connected franchise:

```
FRANCHISE_TYPES = {PREQUEL, SEQUEL, PARENT, SIDE_STORY, ALTERNATIVE}
MAX_NODES = 50      # cap on AniList queries per assembly
MAX_DEPTH = 6

nodes = {}                       # anilist_id -> display dict
queue = deque([(start_id, 0)])
enqueued = {start_id}
while queue and queries_made < MAX_NODES:
    cur, depth = queue.popleft()
    try:
        data = client.get_anime_relations(cur)   # cached per id
    except AniListError:
        continue                                  # skip this node, keep going
    queries_made += 1
    nodes[cur] = data["self"]                     # authoritative self data
    if depth >= MAX_DEPTH:
        continue
    for edge in data["edges"]:
        n = edge["node"]
        if n["type"] != "ANIME":                continue
        if edge["relation_type"] not in FRANCHISE_TYPES: continue
        nodes.setdefault(n["anilist_id"], n)      # stub display data if unseen
        if n["anilist_id"] not in enqueued:
            enqueued.add(n["anilist_id"])
            queue.append((n["anilist_id"], depth + 1))
return nodes
```

- `MAX_NODES` bounds API calls (and runaway franchises); `MAX_DEPTH` bounds
  chain length. Leaf nodes beyond the caps still display via stub data from
  their parent's edges.
- Cycles are handled by `enqueued`.
- Caps are constants, easily tuned.

### Filtering, mapping, sorting

- **Relation-type filter:** `FRANCHISE_TYPES` allowlist (above). Excludes
  ADAPTATION, CHARACTER, SPIN_OFF, SUMMARY, OTHER, SOURCE, COMPILATION,
  CONTAINS. Single constant — easy to adjust later.
- **Type filter:** `node.type == "ANIME"` only (drops manga/novel relations).
- **Catalog mapping:** for each assembled node, look up a local `Anime` by
  `anilist_id` (single `IN` query for all ids). If found → set `id`, prefer the
  local `image_url`/`title`; else → `id = null`, use AniList cover/title.
- **Current title:** the start node gets `is_current = true`; it is always
  included.
- **Sorting:** ascending by `(year or 9999, month or 99, day or 99, title)` so
  dated entries lead and undated ones sort last deterministically.
- **Format label map:** `TV→"TV"`, `TV_SHORT→"TV Short"`, `MOVIE→"Movie"`,
  `SPECIAL→"Special"`, `OVA→"OVA"`, `ONA→"ONA"`, `MUSIC→"Music"`, else `null`.

## Frontend design

### Types — `frontend/src/types/api.ts`

```ts
export interface RelatedEntry {
  anilist_id: number;
  id: number | null;          // local Bingery id, or null if not in catalog
  title: string;
  format: string | null;
  release_date: string | null;
  year: number | null;
  image_url: string | null;
  is_current: boolean;
}
export interface RelatedResponse { related: RelatedEntry[]; }
```

### API client — `frontend/src/lib/api.ts`

```ts
getRelated: (id: number) => request<RelatedResponse>(`/anime/${id}/related`),
```

### Hook — `frontend/src/hooks/useAnimeDetail.ts`

`useRelated(id)`, mirroring `useSimilar` (React Query, key
`["anime-related", id]`, enabled when `id` is defined).

### Component — `frontend/src/features/details/RelatedStrip.tsx`

- Renders a **wrapping** responsive grid reusing the SimilarStrip rhythm:
  `grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4`. Cards
  flow onto new lines automatically — no horizontal scroll.
- Each card: poster (aspect 2/3), title (truncated to ~2 lines), a small format
  badge, and the release date (full date if known, else year, else "TBA").
- Catalog entries (`id != null`) wrap in `<Link to={/anime/${id}}>`; others
  render as a static card (subtle "not in library" affordance optional).
- Current entry (`is_current`): accent ring/border + a "Current" tag; not a
  link.
- Returns `null` when `related.length <= 1` (nothing meaningful to show).

### Placement — `frontend/src/features/details/AnimeDetailPage.tsx`

- Add `useRelated(numericId)`.
- Render `<RelatedStrip related={related.data?.related ?? []} />` immediately
  after the **Community fan genres** `<section>` and before **Your rating**.
- Section header: "Watch the rest in order!".

## Edge cases

- **No `anilist_id`** on the anime → empty list → section hidden.
- **AniList unreachable / timeout** → endpoint returns `[]` (200); section
  hidden; rest of page unaffected (separate query, like `useSimilar`).
- **Standalone anime** (no franchise edges) → single entry → section hidden.
- **Missing dates** → sorted last; display year or "TBA".
- **Huge franchise** → capped at `MAX_NODES`; remaining entries omitted
  (acceptable for v1; caps tunable).
- **Non-catalog entries** → rendered from AniList data, non-clickable.

## Testing

- `tests/test_related.py` (pytest, AniList client mocked to return a small
  synthetic franchise graph). Assertions:
  - Traversal assembles the full graph across multiple hops (not just one-hop).
  - Relation-type allowlist enforced; non-ANIME nodes dropped.
  - Current title injected with `is_current = true` and always present.
  - Sorted ascending by release date; undated entries last.
  - Format labels mapped correctly.
  - Local catalog mapping sets `id` for known `anilist_id`s, `null` otherwise.
  - `anilist_id is None` and AniList-error paths both return `[]`.
- `tsc -b` clean for the frontend changes.
- Manual: open a multi-entry franchise (e.g. Attack on Titan) on a running
  instance; confirm full chronological strip, format badges, current-title
  highlight, wrapping layout, and that catalog links navigate.

## Files touched

- `utils/anilist.py` — `RELATIONS_QUERY`, `get_anime_relations`, TTL cache.
- `routes/anime.py` — `GET /<int:anime_id>/related`, franchise assembly + map.
- `tests/test_related.py` — new test module.
- `frontend/src/types/api.ts` — `RelatedEntry`, `RelatedResponse`.
- `frontend/src/lib/api.ts` — `getRelated`.
- `frontend/src/hooks/useAnimeDetail.ts` — `useRelated`.
- `frontend/src/features/details/RelatedStrip.tsx` — new component.
- `frontend/src/features/details/AnimeDetailPage.tsx` — wire + place section.

## Out of scope / future

- Persisting relations/format/dates in the DB.
- "Import on click" for non-catalog entries (create a local record on demand).
- Including spin-offs, adaptations, recaps/summaries, or compilations
  (adjustable via the `FRANCHISE_TYPES` constant).
- Cross-request shared cache (Redis) — only needed if scaled past one worker.
