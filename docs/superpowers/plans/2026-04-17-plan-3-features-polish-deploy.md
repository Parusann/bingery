# Bingery Features, Polish, and Deploy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the five new Bingery features (Collections, Stats, Seasonal, Activity, Compare) with polished motion, code-split routes, optimized images, and production deploy configuration — cutting Flask over permanently to the Vite build and archiving the legacy single-file `static/index.html`.

**Architecture:** Feature UIs consume the Plan 1 backend endpoints (`/api/collections`, `/api/stats`, `/api/seasonal`, `/api/activity`, `/api/compare`). Each feature follows the same pattern: typed hooks in `src/hooks/`, types in `src/types/api.ts`, components scoped under `src/features/<feature>/`, route added in `src/routes.tsx`, nav entry added in `src/layout/NavBar.tsx`. Polish pass adds staggered scroll reveals, image blur-up, and React.lazy code splitting to shrink the initial JS bundle. Production deploy uses Render with `build.sh` that installs Python deps and builds the frontend; `render.yaml` declares both AI providers so the box can switch at runtime via env var. The legacy `static/index.html` is moved to `legacy/index.html.bak` (kept for reference, not served).

**Tech Stack:** Same as Plan 2 (Vite, React, TS, Tailwind, Framer Motion, TanStack Query, Zustand, LiquidGL). Adds `react-intersection-observer` for scroll reveals and `react-window` is **not** used (grids are short enough). Playwright gains a multi-page flow test.

---

## File Structure Map

```
frontend/src/
├── types/
│   ├── models.ts                                # add Collection, CollectionItem, StatsOverview, etc.
│   └── api.ts                                   # add new response types
├── hooks/
│   ├── useCollections.ts                        # list, detail, create/update/delete, add/remove items
│   ├── useStats.ts                              # overview + heatmap
│   ├── useSeasonal.ts                           # current + historical season
│   ├── useActivity.ts                           # paginated timeline
│   └── useCompare.ts                            # compare two users
├── features/
│   ├── collections/
│   │   ├── CollectionsListPage.tsx
│   │   ├── CollectionDetailPage.tsx
│   │   ├── CollectionCard.tsx
│   │   ├── CollectionForm.tsx                   # create/edit modal body
│   │   ├── AddToCollection.tsx                  # inline selector for detail page
│   │   └── ShareButton.tsx                      # copy share link
│   ├── stats/
│   │   ├── StatsPage.tsx
│   │   ├── OverviewCards.tsx                    # big numbers
│   │   ├── RatingHistogram.tsx
│   │   ├── GenreBreakdown.tsx
│   │   └── ActivityHeatmap.tsx                  # GitHub-style calendar
│   ├── seasonal/
│   │   ├── SeasonalPage.tsx
│   │   └── SeasonPicker.tsx
│   ├── activity/
│   │   ├── ActivityPage.tsx
│   │   └── ActivityEntry.tsx
│   └── compare/
│       ├── ComparePage.tsx
│       ├── UserPicker.tsx
│       └── TasteVenn.tsx                        # SVG overlap viz
├── design/
│   └── ScrollReveal.tsx                         # IO-triggered fade + slide
├── layout/
│   └── NavBar.tsx                               # add new entries
└── routes.tsx                                   # add + lazy-load all feature routes

frontend/
├── package.json                                 # add react-intersection-observer
└── e2e/
    ├── smoke.spec.ts                            # extended
    └── full-flow.spec.ts                        # new end-to-end scenario

root/
├── render.yaml                                  # updated env + build
├── build.sh                                     # (finalized)
├── README.md                                    # untouched unless user asks
├── legacy/
│   └── index.html.bak                           # archived legacy frontend
└── static/
    └── .gitkeep                                 # kept empty to satisfy Flask fallback check
```

---

## Task 1: Collections hook + API types

**Files:**
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/hooks/useCollections.ts`

- [ ] **Step 1: Append collection types to `frontend/src/types/models.ts`**

Open the file and append after the existing exports:

```ts
export interface Collection {
  id: number;
  owner_id: number;
  title: string;
  description: string | null;
  is_public: boolean;
  share_token: string | null;
  item_count: number;
  cover_image_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface CollectionItem {
  id: number;
  anime: AnimeSummary;
  note: string | null;
  position: number;
  added_at: string;
}

export interface CollectionDetail extends Collection {
  items: CollectionItem[];
  owner: { id: number; username: string; display_name: string | null };
}
```

- [ ] **Step 2: Append response types to `frontend/src/types/api.ts`**

Open and append:

```ts
import type { Collection, CollectionDetail } from "./models";

export interface CollectionsListResponse {
  collections: Collection[];
}

export interface CollectionResponse {
  collection: CollectionDetail;
}

export interface CollectionMutation {
  collection: Collection;
}
```

- [ ] **Step 3: Extend `frontend/src/lib/api.ts` with collections endpoints**

Open `frontend/src/lib/api.ts` and add to the `api` object (just before the closing `}`; match the existing style of arrow functions calling `request`):

```ts
  getCollections: () =>
    request<import("@/types/api").CollectionsListResponse>("/collections"),
  getCollection: (id: number) =>
    request<import("@/types/api").CollectionResponse>(`/collections/${id}`),
  getSharedCollection: (token: string) =>
    request<import("@/types/api").CollectionResponse>(`/collections/share/${token}`),
  createCollection: (body: {
    title: string;
    description?: string;
    is_public?: boolean;
  }) =>
    request<import("@/types/api").CollectionMutation>("/collections", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateCollection: (
    id: number,
    body: { title?: string; description?: string; is_public?: boolean }
  ) =>
    request<import("@/types/api").CollectionMutation>(`/collections/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteCollection: (id: number) =>
    request<{ ok: boolean }>(`/collections/${id}`, { method: "DELETE" }),
  addToCollection: (
    id: number,
    body: { anime_id: number; note?: string }
  ) =>
    request<{ item: import("@/types/models").CollectionItem }>(
      `/collections/${id}/items`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  removeFromCollection: (id: number, animeId: number) =>
    request<{ ok: boolean }>(`/collections/${id}/items/${animeId}`, {
      method: "DELETE",
    }),
```

- [ ] **Step 4: Create `frontend/src/hooks/useCollections.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCollections() {
  return useQuery({
    queryKey: ["collections"],
    queryFn: () => api.getCollections(),
  });
}

export function useCollection(id: number | undefined) {
  return useQuery({
    queryKey: ["collection", id],
    queryFn: () => api.getCollection(id!),
    enabled: !!id,
  });
}

export function useSharedCollection(token: string | undefined) {
  return useQuery({
    queryKey: ["collection-share", token],
    queryFn: () => api.getSharedCollection(token!),
    enabled: !!token,
  });
}

export function useCreateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description?: string; is_public?: boolean }) =>
      api.createCollection(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });
}

export function useUpdateCollection(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title?: string; description?: string; is_public?: boolean }) =>
      api.updateCollection(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["collection", id] });
    },
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteCollection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });
}

export function useAddToCollection(collectionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { anime_id: number; note?: string }) =>
      api.addToCollection(collectionId, body),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["collection", collectionId] }),
  });
}

export function useRemoveFromCollection(collectionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) =>
      api.removeFromCollection(collectionId, animeId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["collection", collectionId] }),
  });
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/hooks/useCollections.ts
git commit -m "Add collection types, API client methods, and query hooks"
```

---

## Task 2: Collections list page + CollectionCard

**Files:**
- Create: `frontend/src/features/collections/CollectionCard.tsx`
- Create: `frontend/src/features/collections/CollectionsListPage.tsx`

- [ ] **Step 1: Create `frontend/src/features/collections/CollectionCard.tsx`**

```tsx
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { Collection } from "@/types/models";
import { Badge } from "@/design/Badge";
import { transitions } from "@/design/motion";

export function CollectionCard({
  collection,
  index = 0,
}: {
  collection: Collection;
  index?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...transitions.ease, delay: Math.min(index, 10) * 0.03 }}
    >
      <Link
        to={`/collections/${collection.id}`}
        className="block rounded-xl overflow-hidden border border-border bg-surface hover:border-border-strong transition-colors glass-edge"
      >
        <div className="relative aspect-[5/3] bg-black/40 overflow-hidden">
          {collection.cover_image_url ? (
            <img
              src={collection.cover_image_url}
              alt=""
              loading="lazy"
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-amber/20 via-transparent to-violet/20" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2">
            <h3 className="font-display text-xl truncate">{collection.title}</h3>
            {collection.is_public ? (
              <Badge color="#8fc9a4">Public</Badge>
            ) : (
              <Badge color="#b89ac4">Private</Badge>
            )}
          </div>
        </div>
        <div className="p-3 text-sm text-text-muted flex items-center justify-between">
          <span>{collection.item_count} anime</span>
          <span className="font-mono text-xs">
            {new Date(collection.updated_at).toLocaleDateString()}
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/collections/CollectionsListPage.tsx`**

```tsx
import { useState } from "react";
import { Button } from "@/design/Button";
import { Modal } from "@/design/Modal";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useCollections } from "@/hooks/useCollections";
import { CollectionCard } from "./CollectionCard";
import { CollectionForm } from "./CollectionForm";

export function CollectionsListPage() {
  const user = useAuth((s) => s.user);
  const { data, isLoading } = useCollections();
  const [creating, setCreating] = useState(false);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in to build collections</h1>
        <p className="text-text-muted">
          Organize anime into private or shareable lists.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h1 className="font-display text-4xl text-amber">Collections</h1>
        <Button className="ml-auto" onClick={() => setCreating(true)}>
          New collection
        </Button>
      </div>
      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48" rounded="lg" />
          ))}
        </div>
      ) : data && data.collections.length ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.collections.map((c, i) => (
            <CollectionCard key={c.id} collection={c} index={i} />
          ))}
        </div>
      ) : (
        <div className="py-20 text-center text-text-muted">
          No collections yet. Start one above.
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)}>
        <div className="p-6">
          <h2 className="font-display text-2xl mb-4">New collection</h2>
          <CollectionForm onSuccess={() => setCreating(false)} />
        </div>
      </Modal>
    </div>
  );
}
```

- [ ] **Step 3: Commit (skeleton — Form created in Task 3)**

```bash
git add frontend/src/features/collections/CollectionCard.tsx frontend/src/features/collections/CollectionsListPage.tsx
git commit -m "Add collections list page and collection card"
```

---

## Task 3: CollectionForm + create/edit flows

**Files:**
- Create: `frontend/src/features/collections/CollectionForm.tsx`

- [ ] **Step 1: Create `frontend/src/features/collections/CollectionForm.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Collection } from "@/types/models";
import { Button } from "@/design/Button";
import { Input } from "@/design/Input";
import {
  useCreateCollection,
  useUpdateCollection,
} from "@/hooks/useCollections";

interface Props {
  initial?: Collection;
  onSuccess?: (c: Collection) => void;
}

export function CollectionForm({ initial, onSuccess }: Props) {
  const nav = useNavigate();
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isPublic, setIsPublic] = useState(initial?.is_public ?? false);
  const create = useCreateCollection();
  const update = useUpdateCollection(initial?.id ?? -1);
  const busy = create.isPending || update.isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = {
          title: title.trim(),
          description: description.trim() || undefined,
          is_public: isPublic,
        };
        try {
          if (initial) {
            const r = await update.mutateAsync(body);
            onSuccess?.(r.collection);
          } else {
            const r = await create.mutateAsync(body);
            onSuccess?.(r.collection);
            nav(`/collections/${r.collection.id}`);
          }
        } catch {
          /* handled in ui via mutation error state */
        }
      }}
    >
      <Input
        label="Title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
      />
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="text-text-muted">Description</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="min-h-[80px] px-3 py-2 rounded-lg bg-surface border border-border focus:border-border-strong outline-none text-sm"
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={isPublic}
          onChange={(e) => setIsPublic(e.target.checked)}
        />
        <span className="text-text-muted">
          Public — anyone with the share link can view
        </span>
      </label>
      <div className="flex gap-3">
        <Button type="submit" loading={busy} disabled={!title.trim()}>
          {initial ? "Save changes" : "Create collection"}
        </Button>
        {create.isError || update.isError ? (
          <span className="text-sm text-danger">
            {(create.error || update.error)?.message}
          </span>
        ) : null}
      </div>
    </form>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/collections/CollectionForm.tsx
git commit -m "Add collection create/edit form with public toggle"
```

---

## Task 4: Collection detail page + share button + AddToCollection

**Files:**
- Create: `frontend/src/features/collections/ShareButton.tsx`
- Create: `frontend/src/features/collections/AddToCollection.tsx`
- Create: `frontend/src/features/collections/CollectionDetailPage.tsx`

- [ ] **Step 1: Create `frontend/src/features/collections/ShareButton.tsx`**

```tsx
import { useState } from "react";
import { Button } from "@/design/Button";

export function ShareButton({ token }: { token: string | null }) {
  const [copied, setCopied] = useState(false);
  if (!token) return null;
  const url = `${window.location.origin}/collections/share/${token}`;
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={async () => {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Link copied" : "Copy share link"}
    </Button>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/collections/AddToCollection.tsx`**

```tsx
import { useState } from "react";
import { Button } from "@/design/Button";
import {
  useAddToCollection,
  useCollections,
  useCreateCollection,
} from "@/hooks/useCollections";

interface Props {
  animeId: number;
}

export function AddToCollection({ animeId }: Props) {
  const { data } = useCollections();
  const [open, setOpen] = useState(false);
  const create = useCreateCollection();
  const [newTitle, setNewTitle] = useState("");
  const collections = data?.collections ?? [];

  return (
    <div className="relative">
      <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
        Add to collection
      </Button>
      {open ? (
        <div className="absolute right-0 top-full mt-2 z-10 w-72 rounded-lg border border-border bg-bg-elevated glass-edge p-3 space-y-2">
          {collections.length === 0 ? (
            <p className="text-xs text-text-muted px-1 py-2">
              No collections yet. Create one below.
            </p>
          ) : (
            <div className="max-h-56 overflow-y-auto">
              {collections.map((c) => (
                <AddRow key={c.id} collectionId={c.id} title={c.title} animeId={animeId} />
              ))}
            </div>
          )}
          <form
            className="flex gap-2 pt-2 border-t border-border"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!newTitle.trim()) return;
              const r = await create.mutateAsync({ title: newTitle.trim() });
              setNewTitle("");
              await new Promise((res) => setTimeout(res, 60));
              const item = document.querySelector<HTMLButtonElement>(
                `[data-add-row="${r.collection.id}"]`
              );
              item?.click();
            }}
          >
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="New collection title…"
              className="flex-1 h-8 px-2 rounded-md bg-surface border border-border text-sm outline-none"
            />
            <Button size="sm" type="submit" disabled={!newTitle.trim()}>
              Add
            </Button>
          </form>
        </div>
      ) : null}
    </div>
  );
}

function AddRow({
  collectionId,
  title,
  animeId,
}: {
  collectionId: number;
  title: string;
  animeId: number;
}) {
  const add = useAddToCollection(collectionId);
  const [done, setDone] = useState(false);
  return (
    <button
      data-add-row={collectionId}
      onClick={async () => {
        try {
          await add.mutateAsync({ anime_id: animeId });
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* toast later */
        }
      }}
      className="w-full text-left text-sm px-2 py-2 rounded-md hover:bg-white/[0.05] flex items-center justify-between"
    >
      <span>{title}</span>
      <span className="text-xs text-text-muted">
        {add.isPending ? "…" : done ? "✓" : "+"}
      </span>
    </button>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/collections/CollectionDetailPage.tsx`**

```tsx
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Modal } from "@/design/Modal";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { AnimeCard } from "@/features/discover/AnimeCard";
import { useAuth } from "@/stores/auth";
import {
  useCollection,
  useDeleteCollection,
  useRemoveFromCollection,
} from "@/hooks/useCollections";
import { CollectionForm } from "./CollectionForm";
import { ShareButton } from "./ShareButton";

export function CollectionDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const numericId = id ? Number(id) : undefined;
  const user = useAuth((s) => s.user);
  const { data, isLoading } = useCollection(numericId);
  const del = useDeleteCollection();
  const remove = useRemoveFromCollection(numericId ?? -1);
  const [editing, setEditing] = useState(false);

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16" rounded="lg" />
        <Skeleton className="h-64" rounded="lg" />
      </div>
    );
  }
  const c = data.collection;
  const isOwner = user?.id === c.owner_id;

  return (
    <article>
      <header className="flex flex-col gap-3 mb-6">
        <div className="flex flex-wrap items-baseline gap-3">
          <h1 className="font-display text-4xl text-amber">{c.title}</h1>
          <span className="text-sm text-text-muted">
            by {c.owner.display_name ?? c.owner.username}
          </span>
          <div className="ml-auto flex gap-2">
            <ShareButton token={c.share_token} />
            {isOwner ? (
              <>
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={async () => {
                    if (!window.confirm("Delete this collection?")) return;
                    await del.mutateAsync(c.id);
                    nav("/collections");
                  }}
                >
                  Delete
                </Button>
              </>
            ) : null}
          </div>
        </div>
        {c.description ? (
          <p className="text-text-muted max-w-3xl">{c.description}</p>
        ) : null}
      </header>

      {c.items.length === 0 ? (
        <GlassCard className="p-10 text-center text-text-muted">
          This collection is empty.{" "}
          {isOwner
            ? "Add anime from the discover or detail page."
            : "Nothing here yet."}
        </GlassCard>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {c.items.map((it, i) => (
            <div key={it.id} className="relative group">
              <AnimeCard anime={it.anime} index={i} />
              {isOwner ? (
                <button
                  onClick={() => remove.mutate(it.anime.id)}
                  className="absolute top-2 left-2 px-2 py-0.5 text-xs rounded-md bg-black/60 text-danger opacity-0 group-hover:opacity-100 transition-opacity"
                  aria-label="Remove"
                >
                  Remove
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <Modal open={editing} onClose={() => setEditing(false)}>
        <div className="p-6">
          <h2 className="font-display text-2xl mb-4">Edit collection</h2>
          <CollectionForm initial={c} onSuccess={() => setEditing(false)} />
        </div>
      </Modal>
    </article>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/collections/ShareButton.tsx frontend/src/features/collections/AddToCollection.tsx frontend/src/features/collections/CollectionDetailPage.tsx
git commit -m "Add collection detail page with edit, share, and owner controls"
```

---

## Task 5: Integrate AddToCollection into anime detail page + WatchStatusSelector

**Files:**
- Modify: `frontend/src/features/details/AnimeDetailPage.tsx`
- Modify: `frontend/src/features/details/DetailHero.tsx`

- [ ] **Step 1: Update `frontend/src/features/details/DetailHero.tsx` to accept an action slot**

Find the DetailHero component and add an `actions` prop, then render it above the stats grid:

```tsx
// ... existing imports ...
import type { ReactNode } from "react";

interface HeroProps {
  anime: AnimeDetail;
  actions?: ReactNode;
}

export function DetailHero({ anime, actions }: HeroProps) {
  // ... existing body ...
  // Replace the existing flex-wrap genre badges block with:
  //    <div className="flex flex-wrap items-center gap-2 mb-4">
  //      <div className="flex flex-wrap gap-1.5">
  //        {genres.slice(0, 6).map(...)}
  //      </div>
  //      {actions ? <div className="ml-auto flex gap-2">{actions}</div> : null}
  //    </div>
}
```

Rewrite the whole file as:

```tsx
import type { ReactNode } from "react";
import type { AnimeDetail } from "@/types/models";
import { LiquidGLSurface } from "@/design/LiquidGLSurface";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

interface HeroProps {
  anime: AnimeDetail;
  actions?: ReactNode;
}

export function DetailHero({ anime, actions }: HeroProps) {
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g) => (typeof g === "string" ? g : g.name))
    .filter(Boolean) as string[];
  return (
    <div className="relative overflow-hidden rounded-xl mb-6">
      {anime.banner_url ? (
        <img
          src={anime.banner_url}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
      ) : null}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/80 to-transparent" />
      <LiquidGLSurface className="relative z-10 p-6 md:p-10 flex flex-col md:flex-row gap-6">
        {anime.image_url ? (
          <img
            src={anime.image_url}
            alt=""
            className="w-40 md:w-56 aspect-[2/3] rounded-lg object-cover shrink-0 shadow-2xl"
          />
        ) : null}
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-4xl md:text-5xl mb-2">
            {anime.title_english ?? anime.title}
          </h1>
          {anime.title_english && anime.title !== anime.title_english ? (
            <p className="text-text-muted mb-3">{anime.title}</p>
          ) : null}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="flex flex-wrap gap-1.5">
              {genres.slice(0, 6).map((g) => (
                <Badge key={g} color={genreColor(g)}>
                  {g}
                </Badge>
              ))}
            </div>
            {actions ? (
              <div className="ml-auto flex flex-wrap gap-2">{actions}</div>
            ) : null}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Stat label="Episodes" value={anime.episodes ?? "—"} />
            <Stat label="Year" value={anime.year ?? "—"} />
            <Stat label="Format" value={anime.format ?? "—"} />
            <Stat label="Score" value={anime.api_score?.toFixed(1) ?? "—"} />
          </div>
          {anime.description ? (
            <p className="mt-5 text-text-muted leading-relaxed max-w-3xl">
              {anime.description.replace(/<[^>]+>/g, "")}
            </p>
          ) : null}
        </div>
      </LiquidGLSurface>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs text-text-dim uppercase tracking-wider">{label}</div>
      <div className="text-lg font-mono text-amber">{value}</div>
    </div>
  );
}
```

- [ ] **Step 2: Update `frontend/src/features/details/AnimeDetailPage.tsx` to pass hero actions**

Replace the whole file with:

```tsx
import { useParams } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { useAnimeDetail, useSimilar } from "@/hooks/useAnimeDetail";
import { WatchStatusSelector } from "@/features/watchlist/WatchStatusSelector";
import { AddToCollection } from "@/features/collections/AddToCollection";
import { useAuth } from "@/stores/auth";
import { DetailHero } from "./DetailHero";
import { FanGenreBars } from "./FanGenreBars";
import { RatingPanel } from "./RatingPanel";
import { SimilarStrip } from "./SimilarStrip";

export function AnimeDetailPage() {
  const { id } = useParams();
  const numericId = id ? Number(id) : undefined;
  const user = useAuth((s) => s.user);
  const detail = useAnimeDetail(numericId);
  const similar = useSimilar(numericId);

  if (detail.isLoading || !detail.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-72" rounded="lg" />
        <Skeleton className="h-48" rounded="lg" />
      </div>
    );
  }
  const anime = detail.data.anime;
  const actions = user ? (
    <>
      <WatchStatusSelector
        animeId={anime.id}
        current={anime.user_watch_status?.status ?? null}
        isFavorite={anime.user_watch_status?.is_favorite ?? false}
      />
      <AddToCollection animeId={anime.id} />
    </>
  ) : null;

  return (
    <article>
      <DetailHero anime={anime} actions={actions} />
      <div className="grid md:grid-cols-[1fr_420px] gap-8">
        <section>
          <h2 className="font-display text-2xl mb-4">Community fan genres</h2>
          <GlassCard className="p-6">
            {anime.fan_genres && anime.fan_genres.length ? (
              <FanGenreBars fanGenres={anime.fan_genres} />
            ) : (
              <p className="text-text-muted text-sm">
                No fan-genre votes yet. Be the first.
              </p>
            )}
          </GlassCard>
        </section>
        <aside>
          <h2 className="font-display text-2xl mb-4">Your rating</h2>
          <GlassCard tone="warm" className="p-6">
            <RatingPanel anime={anime} />
          </GlassCard>
        </aside>
      </div>
      <SimilarStrip similar={similar.data?.similar ?? []} />
    </article>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/details/DetailHero.tsx frontend/src/features/details/AnimeDetailPage.tsx
git commit -m "Integrate watchlist selector and add-to-collection into anime detail"
```

---

## Task 6: Stats hook + overview page

**Files:**
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useStats.ts`
- Create: `frontend/src/features/stats/OverviewCards.tsx`
- Create: `frontend/src/features/stats/StatsPage.tsx`

- [ ] **Step 1: Append stats types to `frontend/src/types/models.ts`**

```ts
export interface StatsOverview {
  total_rated: number;
  total_watched: number;
  hours_watched: number;
  favorite_count: number;
  avg_rating: number | null;
  top_genre: string | null;
  streak_days: number;
}

export interface StatsHeatmapCell {
  date: string;
  count: number;
}

export interface StatsHeatmap {
  cells: StatsHeatmapCell[];
  max: number;
}

export interface StatsGenreSlice {
  genre: string;
  count: number;
}

export interface StatsRatingBucket {
  score: number;
  count: number;
}

export interface StatsOverviewResponse {
  overview: StatsOverview;
  rating_distribution: StatsRatingBucket[];
  top_genres: StatsGenreSlice[];
}
```

- [ ] **Step 2: Append stats response types to `frontend/src/types/api.ts`**

```ts
import type { StatsHeatmap, StatsOverviewResponse } from "./models";

export interface StatsOverviewResp extends StatsOverviewResponse {}
export interface StatsHeatmapResp {
  heatmap: StatsHeatmap;
}
```

- [ ] **Step 3: Add stats endpoints to `frontend/src/lib/api.ts`**

Inside the `api` object, add:

```ts
  getStatsOverview: () =>
    request<import("@/types/api").StatsOverviewResp>("/stats/overview"),
  getStatsHeatmap: () =>
    request<import("@/types/api").StatsHeatmapResp>("/stats/heatmap"),
```

- [ ] **Step 4: Create `frontend/src/hooks/useStats.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useStatsOverview(enabled = true) {
  return useQuery({
    queryKey: ["stats-overview"],
    queryFn: () => api.getStatsOverview(),
    enabled,
    staleTime: 60_000,
  });
}

export function useStatsHeatmap(enabled = true) {
  return useQuery({
    queryKey: ["stats-heatmap"],
    queryFn: () => api.getStatsHeatmap(),
    enabled,
    staleTime: 60_000,
  });
}
```

- [ ] **Step 5: Create `frontend/src/features/stats/OverviewCards.tsx`**

```tsx
import type { StatsOverview } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

const cards: Array<{
  key: keyof StatsOverview;
  label: string;
  format?: (v: unknown) => string;
}> = [
  { key: "total_rated", label: "Ratings" },
  { key: "total_watched", label: "Completed" },
  {
    key: "hours_watched",
    label: "Hours watched",
    format: (v) => Math.round(Number(v ?? 0)).toString(),
  },
  { key: "favorite_count", label: "Favorites" },
  {
    key: "avg_rating",
    label: "Avg rating",
    format: (v) => (v == null ? "—" : `${Number(v).toFixed(1)}/10`),
  },
  { key: "streak_days", label: "Streak (days)" },
];

export function OverviewCards({ overview }: { overview: StatsOverview }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => {
        const raw = overview[c.key];
        const formatted = c.format ? c.format(raw) : String(raw ?? "—");
        return (
          <GlassCard key={c.key} tone="warm" className="p-4">
            <div className="text-xs uppercase tracking-wider text-text-dim">
              {c.label}
            </div>
            <div className="font-display text-3xl text-amber mt-1 tabular-nums">
              {formatted}
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend/src/features/stats/StatsPage.tsx` (minimal; charts arrive in Task 7)**

```tsx
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useStatsOverview } from "@/hooks/useStats";
import { OverviewCards } from "./OverviewCards";

export function StatsPage() {
  const user = useAuth((s) => s.user);
  const overview = useStatsOverview(!!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in for your stats</h1>
        <p className="text-text-muted">
          See your rating distribution, heatmap, and top genres.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="font-display text-4xl text-amber">Your stats</h1>
      {overview.isLoading || !overview.data ? (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20" rounded="lg" />
          ))}
        </div>
      ) : (
        <OverviewCards overview={overview.data.overview} />
      )}
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/hooks/useStats.ts frontend/src/features/stats/OverviewCards.tsx frontend/src/features/stats/StatsPage.tsx
git commit -m "Add stats overview page with summary cards"
```

---

## Task 7: Rating histogram + genre breakdown + heatmap

**Files:**
- Create: `frontend/src/features/stats/RatingHistogram.tsx`
- Create: `frontend/src/features/stats/GenreBreakdown.tsx`
- Create: `frontend/src/features/stats/ActivityHeatmap.tsx`
- Modify: `frontend/src/features/stats/StatsPage.tsx`

- [ ] **Step 1: Create `frontend/src/features/stats/RatingHistogram.tsx`**

```tsx
import type { StatsRatingBucket } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

export function RatingHistogram({ buckets }: { buckets: StatsRatingBucket[] }) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <GlassCard className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl">Rating distribution</h2>
        <span className="text-xs text-text-dim uppercase tracking-wider">
          1 — 10
        </span>
      </div>
      <div className="grid grid-cols-10 gap-2 items-end h-40">
        {Array.from({ length: 10 }).map((_, i) => {
          const score = i + 1;
          const bucket = buckets.find((b) => b.score === score);
          const count = bucket?.count ?? 0;
          const h = (count / max) * 100;
          return (
            <div key={score} className="flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t-sm bg-gradient-to-t from-amber to-amber-soft"
                style={{ height: `${Math.max(2, h)}%` }}
                title={`${count} at ${score}/10`}
              />
              <div className="text-xs text-text-muted tabular-nums">{score}</div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/stats/GenreBreakdown.tsx`**

```tsx
import type { StatsGenreSlice } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { genreColor } from "@/lib/genres";

export function GenreBreakdown({ slices }: { slices: StatsGenreSlice[] }) {
  const total = slices.reduce((n, s) => n + s.count, 0);
  return (
    <GlassCard tone="cool" className="p-6">
      <h2 className="font-display text-xl mb-4">Top genres</h2>
      <div className="space-y-2">
        {slices.slice(0, 8).map((s) => {
          const pct = total > 0 ? (s.count / total) * 100 : 0;
          return (
            <div key={s.genre} className="flex items-center gap-3 text-sm">
              <div className="w-32 shrink-0 text-text-muted">{s.genre}</div>
              <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full"
                  style={{ width: `${pct}%`, background: genreColor(s.genre) }}
                />
              </div>
              <div className="w-10 text-right font-mono text-text-muted tabular-nums">
                {s.count}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/stats/ActivityHeatmap.tsx`**

```tsx
import type { StatsHeatmap } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

function intensity(count: number, max: number): string {
  if (count === 0) return "rgba(255,255,255,0.04)";
  const pct = Math.min(1, count / Math.max(1, max));
  const alpha = 0.18 + pct * 0.72;
  return `rgba(230,166,128,${alpha.toFixed(2)})`;
}

export function ActivityHeatmap({ data }: { data: StatsHeatmap }) {
  const byDate = new Map(data.cells.map((c) => [c.date, c.count]));
  const end = new Date();
  end.setHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setDate(end.getDate() - 364);
  const startWeekday = start.getDay();
  start.setDate(start.getDate() - startWeekday);

  const cells: Array<{ date: string; count: number }> = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    const iso = cursor.toISOString().slice(0, 10);
    cells.push({ date: iso, count: byDate.get(iso) ?? 0 });
    cursor.setDate(cursor.getDate() + 1);
  }

  const weeks: Array<typeof cells> = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <GlassCard className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl">Activity — last year</h2>
        <span className="text-xs text-text-dim">
          {data.cells.reduce((n, c) => n + c.count, 0)} events
        </span>
      </div>
      <div className="flex gap-0.5 overflow-x-auto">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-0.5">
            {week.map((cell) => (
              <div
                key={cell.date}
                className="w-2.5 h-2.5 rounded-[2px]"
                style={{ background: intensity(cell.count, data.max) }}
                title={`${cell.date} — ${cell.count}`}
              />
            ))}
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 4: Update `frontend/src/features/stats/StatsPage.tsx` to show all sections**

```tsx
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useStatsHeatmap, useStatsOverview } from "@/hooks/useStats";
import { OverviewCards } from "./OverviewCards";
import { RatingHistogram } from "./RatingHistogram";
import { GenreBreakdown } from "./GenreBreakdown";
import { ActivityHeatmap } from "./ActivityHeatmap";

export function StatsPage() {
  const user = useAuth((s) => s.user);
  const overview = useStatsOverview(!!user);
  const heatmap = useStatsHeatmap(!!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in for your stats</h1>
        <p className="text-text-muted">
          See your rating distribution, heatmap, and top genres.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="font-display text-4xl text-amber">Your stats</h1>
      {overview.isLoading || !overview.data ? (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20" rounded="lg" />
          ))}
        </div>
      ) : (
        <OverviewCards overview={overview.data.overview} />
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {overview.data ? (
          <>
            <RatingHistogram buckets={overview.data.rating_distribution} />
            <GenreBreakdown slices={overview.data.top_genres} />
          </>
        ) : (
          <>
            <Skeleton className="h-64" rounded="lg" />
            <Skeleton className="h-64" rounded="lg" />
          </>
        )}
      </div>
      {heatmap.data ? (
        <ActivityHeatmap data={heatmap.data.heatmap} />
      ) : (
        <Skeleton className="h-40" rounded="lg" />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stats/RatingHistogram.tsx frontend/src/features/stats/GenreBreakdown.tsx frontend/src/features/stats/ActivityHeatmap.tsx frontend/src/features/stats/StatsPage.tsx
git commit -m "Add rating histogram, genre breakdown, and activity heatmap to stats page"
```

---

## Task 8: Seasonal hook + page

**Files:**
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useSeasonal.ts`
- Create: `frontend/src/features/seasonal/SeasonPicker.tsx`
- Create: `frontend/src/features/seasonal/SeasonalPage.tsx`

- [ ] **Step 1: Append types**

Append to `frontend/src/types/models.ts`:

```ts
export type Season = "winter" | "spring" | "summer" | "fall";

export interface SeasonalResponse {
  year: number;
  season: Season;
  anime: AnimeSummary[];
}
```

Append to `frontend/src/types/api.ts`:

```ts
import type { SeasonalResponse } from "./models";
export interface SeasonalResp extends SeasonalResponse {}
```

- [ ] **Step 2: Add endpoint to `frontend/src/lib/api.ts`**

```ts
  getSeasonal: (year?: number, season?: import("@/types/models").Season) =>
    request<import("@/types/api").SeasonalResp>(
      `/seasonal${year && season ? `?year=${year}&season=${season}` : ""}`
    ),
```

- [ ] **Step 3: Create `frontend/src/hooks/useSeasonal.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Season } from "@/types/models";

export function useSeasonal(year?: number, season?: Season) {
  return useQuery({
    queryKey: ["seasonal", year ?? "current", season ?? "current"],
    queryFn: () => api.getSeasonal(year, season),
  });
}

export function currentSeason(now = new Date()): { year: number; season: Season } {
  const m = now.getMonth();
  const season: Season =
    m < 3 ? "winter" : m < 6 ? "spring" : m < 9 ? "summer" : "fall";
  return { year: now.getFullYear(), season };
}
```

- [ ] **Step 4: Create `frontend/src/features/seasonal/SeasonPicker.tsx`**

```tsx
import type { Season } from "@/types/models";
import { cn } from "@/lib/cn";

const SEASONS: Season[] = ["winter", "spring", "summer", "fall"];

interface Props {
  year: number;
  season: Season;
  onChange: (year: number, season: Season) => void;
}

export function SeasonPicker({ year, season, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2 items-center">
      <div className="flex gap-1">
        <button
          onClick={() => onChange(year - 1, season)}
          className="h-8 w-8 rounded-md border border-border text-text-muted hover:text-text hover:border-border-strong"
          aria-label="Previous year"
        >
          ‹
        </button>
        <div className="h-8 px-4 rounded-md bg-surface border border-border flex items-center font-mono tabular-nums">
          {year}
        </div>
        <button
          onClick={() => onChange(year + 1, season)}
          className="h-8 w-8 rounded-md border border-border text-text-muted hover:text-text hover:border-border-strong"
          aria-label="Next year"
        >
          ›
        </button>
      </div>
      <div className="flex gap-1">
        {SEASONS.map((s) => (
          <button
            key={s}
            onClick={() => onChange(year, s)}
            className={cn(
              "h-8 px-3 rounded-md border text-sm capitalize",
              season === s
                ? "bg-amber text-bg border-amber"
                : "border-border text-text-muted hover:text-text hover:border-border-strong"
            )}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/src/features/seasonal/SeasonalPage.tsx`**

```tsx
import { useState } from "react";
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { currentSeason, useSeasonal } from "@/hooks/useSeasonal";
import { SeasonPicker } from "./SeasonPicker";

export function SeasonalPage() {
  const initial = currentSeason();
  const [year, setYear] = useState(initial.year);
  const [season, setSeason] = useState(initial.season);
  const q = useSeasonal(year, season);

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center gap-4 mb-6">
        <h1 className="font-display text-4xl text-amber capitalize">
          {season} {year}
        </h1>
        <div className="md:ml-auto">
          <SeasonPicker
            year={year}
            season={season}
            onChange={(y, s) => {
              setYear(y);
              setSeason(s);
            }}
          />
        </div>
      </div>
      <AnimeGrid
        anime={q.data?.anime ?? []}
        loading={q.isLoading}
        empty="No anime found for this season."
      />
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/hooks/useSeasonal.ts frontend/src/features/seasonal/SeasonPicker.tsx frontend/src/features/seasonal/SeasonalPage.tsx
git commit -m "Add seasonal page with year/season picker"
```

---

## Task 9: Activity timeline hook + page

**Files:**
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useActivity.ts`
- Create: `frontend/src/features/activity/ActivityEntry.tsx`
- Create: `frontend/src/features/activity/ActivityPage.tsx`

- [ ] **Step 1: Append types**

Append to `frontend/src/types/models.ts`:

```ts
export type ActivityKind =
  | "rating"
  | "watch_status"
  | "favorite"
  | "collection_item"
  | "collection_create";

export interface ActivityEvent {
  id: number;
  kind: ActivityKind;
  created_at: string;
  anime?: AnimeSummary;
  meta: Record<string, unknown>;
}

export interface ActivityResponse {
  events: ActivityEvent[];
  page: number;
  pages: number;
}
```

Append to `frontend/src/types/api.ts`:

```ts
import type { ActivityResponse } from "./models";
export interface ActivityResp extends ActivityResponse {}
```

- [ ] **Step 2: Add endpoint to `frontend/src/lib/api.ts`**

```ts
  getActivity: (page = 1) =>
    request<import("@/types/api").ActivityResp>(`/activity?page=${page}`),
```

- [ ] **Step 3: Create `frontend/src/hooks/useActivity.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useActivity(page: number, enabled = true) {
  return useQuery({
    queryKey: ["activity", page],
    queryFn: () => api.getActivity(page),
    enabled,
  });
}
```

- [ ] **Step 4: Create `frontend/src/features/activity/ActivityEntry.tsx`**

```tsx
import { Link } from "react-router-dom";
import type { ActivityEvent } from "@/types/models";

function label(ev: ActivityEvent): string {
  const title = ev.anime?.title_english ?? ev.anime?.title ?? "an anime";
  switch (ev.kind) {
    case "rating": {
      const score = (ev.meta.score as number | undefined) ?? null;
      return score ? `Rated ${title} · ${score}/10` : `Rated ${title}`;
    }
    case "watch_status": {
      const status = (ev.meta.status as string | undefined) ?? "updated";
      return `${status.replace(/_/g, " ")} · ${title}`;
    }
    case "favorite":
      return `Favorited ${title}`;
    case "collection_item":
      return `Added ${title} to collection`;
    case "collection_create":
      return `Started a new collection${
        ev.meta.title ? ` — ${ev.meta.title}` : ""
      }`;
    default:
      return "Activity";
  }
}

export function ActivityEntry({ event }: { event: ActivityEvent }) {
  const body = (
    <div className="flex gap-3 items-center">
      {event.anime?.image_url ? (
        <img
          src={event.anime.image_url}
          alt=""
          className="w-10 h-14 rounded object-cover shrink-0"
        />
      ) : (
        <div className="w-10 h-14 rounded bg-white/5 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate capitalize">{label(event)}</div>
        <div className="text-xs text-text-muted">
          {new Date(event.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
  return event.anime?.id ? (
    <Link
      to={`/anime/${event.anime.id}`}
      className="block p-3 rounded-lg border border-border bg-surface hover:border-border-strong transition-colors"
    >
      {body}
    </Link>
  ) : (
    <div className="p-3 rounded-lg border border-border bg-surface">{body}</div>
  );
}
```

- [ ] **Step 5: Create `frontend/src/features/activity/ActivityPage.tsx`**

```tsx
import { useState } from "react";
import { Button } from "@/design/Button";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useActivity } from "@/hooks/useActivity";
import { ActivityEntry } from "./ActivityEntry";

export function ActivityPage() {
  const user = useAuth((s) => s.user);
  const [page, setPage] = useState(1);
  const q = useActivity(page, !!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in for your timeline</h1>
        <p className="text-text-muted">
          See every rating, status change, and collection add.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-6">Activity</h1>
      <div className="space-y-2 max-w-3xl">
        {q.isLoading ? (
          Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-20" rounded="lg" />
          ))
        ) : q.data?.events.length ? (
          q.data.events.map((ev) => <ActivityEntry key={ev.id} event={ev} />)
        ) : (
          <p className="text-text-muted">No activity yet.</p>
        )}
      </div>
      {q.data && q.data.pages > 1 ? (
        <div className="flex items-center gap-3 mt-6 max-w-3xl justify-center">
          <Button
            size="sm"
            variant="ghost"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="text-sm text-text-muted tabular-nums">
            {q.data.page} / {q.data.pages}
          </span>
          <Button
            size="sm"
            variant="ghost"
            disabled={page >= q.data.pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/hooks/useActivity.ts frontend/src/features/activity/ActivityEntry.tsx frontend/src/features/activity/ActivityPage.tsx
git commit -m "Add activity timeline page with paginated events"
```

---

## Task 10: Compare page with user picker and taste overlap

**Files:**
- Modify: `frontend/src/types/models.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useCompare.ts`
- Create: `frontend/src/features/compare/UserPicker.tsx`
- Create: `frontend/src/features/compare/TasteVenn.tsx`
- Create: `frontend/src/features/compare/ComparePage.tsx`

- [ ] **Step 1: Append types**

Append to `frontend/src/types/models.ts`:

```ts
export interface CompareTaste {
  shared_genres: StatsGenreSlice[];
  only_a_genres: StatsGenreSlice[];
  only_b_genres: StatsGenreSlice[];
  shared_anime: AnimeSummary[];
  score_agreement: number;
}

export interface CompareResponse {
  user_a: { id: number; username: string; display_name: string | null };
  user_b: { id: number; username: string; display_name: string | null };
  taste: CompareTaste;
}
```

Append to `frontend/src/types/api.ts`:

```ts
import type { CompareResponse } from "./models";
export interface CompareResp extends CompareResponse {}
```

- [ ] **Step 2: Add endpoint to `frontend/src/lib/api.ts`**

```ts
  getCompare: (a: string, b: string) =>
    request<import("@/types/api").CompareResp>(
      `/compare?user_a=${encodeURIComponent(a)}&user_b=${encodeURIComponent(b)}`
    ),
```

- [ ] **Step 3: Create `frontend/src/hooks/useCompare.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCompare(a: string, b: string, enabled: boolean) {
  return useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => api.getCompare(a, b),
    enabled,
  });
}
```

- [ ] **Step 4: Create `frontend/src/features/compare/UserPicker.tsx`**

```tsx
import { Input } from "@/design/Input";

interface Props {
  a: string;
  b: string;
  onA: (v: string) => void;
  onB: (v: string) => void;
  onSubmit: () => void;
}

export function UserPicker({ a, b, onA, onB, onSubmit }: Props) {
  return (
    <form
      className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end"
      onSubmit={(e) => {
        e.preventDefault();
        if (a.trim() && b.trim()) onSubmit();
      }}
    >
      <Input label="User A" value={a} onChange={(e) => onA(e.target.value)} />
      <Input label="User B" value={b} onChange={(e) => onB(e.target.value)} />
      <button
        type="submit"
        className="h-10 px-4 rounded-lg bg-amber text-bg font-medium disabled:opacity-50"
        disabled={!a.trim() || !b.trim()}
      >
        Compare
      </button>
    </form>
  );
}
```

- [ ] **Step 5: Create `frontend/src/features/compare/TasteVenn.tsx`**

```tsx
import type { CompareTaste } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

export function TasteVenn({ taste, aLabel, bLabel }: { taste: CompareTaste; aLabel: string; bLabel: string }) {
  const shared = taste.shared_genres.length;
  const only_a = taste.only_a_genres.length;
  const only_b = taste.only_b_genres.length;
  return (
    <GlassCard tone="warm" className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl">Taste overlap</h2>
        <span className="text-sm text-text-muted">
          Agreement: {(taste.score_agreement * 100).toFixed(0)}%
        </span>
      </div>
      <div className="relative h-56 flex items-center justify-center">
        <svg
          viewBox="0 0 400 200"
          className="w-full h-full max-w-md"
          aria-label="Venn diagram"
        >
          <circle
            cx="140"
            cy="100"
            r="80"
            fill="rgba(230,166,128,0.25)"
            stroke="rgba(230,166,128,0.5)"
            strokeWidth="1.5"
          />
          <circle
            cx="260"
            cy="100"
            r="80"
            fill="rgba(184,154,196,0.25)"
            stroke="rgba(184,154,196,0.5)"
            strokeWidth="1.5"
          />
          <text x="80" y="108" fontSize="14" fill="rgba(230,166,128,0.95)" fontFamily="Fraunces, serif">
            {aLabel}: {only_a}
          </text>
          <text x="200" y="108" fontSize="14" fill="rgba(255,255,255,0.9)" textAnchor="middle" fontFamily="Fraunces, serif">
            shared: {shared}
          </text>
          <text x="320" y="108" fontSize="14" fill="rgba(184,154,196,0.95)" textAnchor="end" fontFamily="Fraunces, serif">
            {bLabel}: {only_b}
          </text>
        </svg>
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 6: Create `frontend/src/features/compare/ComparePage.tsx`**

```tsx
import { useState } from "react";
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { Skeleton } from "@/design/Skeleton";
import { useCompare } from "@/hooks/useCompare";
import { UserPicker } from "./UserPicker";
import { TasteVenn } from "./TasteVenn";

export function ComparePage() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [submitted, setSubmitted] = useState<{ a: string; b: string } | null>(null);
  const q = useCompare(submitted?.a ?? "", submitted?.b ?? "", !!submitted);

  return (
    <div className="space-y-8 max-w-4xl">
      <h1 className="font-display text-4xl text-amber">Compare taste</h1>
      <UserPicker
        a={a}
        b={b}
        onA={setA}
        onB={setB}
        onSubmit={() => setSubmitted({ a: a.trim(), b: b.trim() })}
      />
      {q.isFetching ? (
        <Skeleton className="h-56" rounded="lg" />
      ) : q.data ? (
        <>
          <TasteVenn
            taste={q.data.taste}
            aLabel={q.data.user_a.display_name ?? q.data.user_a.username}
            bLabel={q.data.user_b.display_name ?? q.data.user_b.username}
          />
          <section>
            <h2 className="font-display text-2xl mb-4">Anime you both rated</h2>
            <AnimeGrid
              anime={q.data.taste.shared_anime}
              empty="No shared anime yet."
            />
          </section>
        </>
      ) : q.isError ? (
        <p className="text-danger">Couldn't compare. Check the usernames.</p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/types/api.ts frontend/src/lib/api.ts frontend/src/hooks/useCompare.ts frontend/src/features/compare/UserPicker.tsx frontend/src/features/compare/TasteVenn.tsx frontend/src/features/compare/ComparePage.tsx
git commit -m "Add compare page with user picker, Venn, and shared-anime grid"
```

---

## Task 11: Wire routes + update NavBar

**Files:**
- Modify: `frontend/src/routes.tsx`
- Modify: `frontend/src/layout/NavBar.tsx`

- [ ] **Step 1: Replace `frontend/src/routes.tsx` with route map that includes new features**

Open the file. Replace the entire route object with:

```tsx
import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";
import { LandingPage } from "@/features/landing/LandingPage";
import { AuthPage } from "@/features/auth/AuthPage";
import { DiscoverPage } from "@/features/discover/DiscoverPage";
import { AnimeDetailPage } from "@/features/details/AnimeDetailPage";
import { WatchlistPage } from "@/features/watchlist/WatchlistPage";
import { ForYouPage } from "@/features/for-you/ForYouPage";
import { ChatPage } from "@/features/chat/ChatPage";
import { CollectionsListPage } from "@/features/collections/CollectionsListPage";
import { CollectionDetailPage } from "@/features/collections/CollectionDetailPage";
import { StatsPage } from "@/features/stats/StatsPage";
import { SeasonalPage } from "@/features/seasonal/SeasonalPage";
import { ActivityPage } from "@/features/activity/ActivityPage";
import { ComparePage } from "@/features/compare/ComparePage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "auth", element: <AuthPage /> },
      { path: "discover", element: <DiscoverPage /> },
      { path: "anime/:id", element: <AnimeDetailPage /> },
      { path: "watchlist", element: <WatchlistPage /> },
      { path: "for-you", element: <ForYouPage /> },
      { path: "chat", element: <ChatPage /> },
      { path: "collections", element: <CollectionsListPage /> },
      { path: "collections/:id", element: <CollectionDetailPage /> },
      { path: "stats", element: <StatsPage /> },
      { path: "seasonal", element: <SeasonalPage /> },
      { path: "activity", element: <ActivityPage /> },
      { path: "compare", element: <ComparePage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
```

- [ ] **Step 2: Update `frontend/src/layout/NavBar.tsx`**

Replace the file with:

```tsx
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";

const items = [
  { to: "/discover", label: "Discover" },
  { to: "/seasonal", label: "Seasonal" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/collections", label: "Collections" },
  { to: "/for-you", label: "For you" },
  { to: "/stats", label: "Stats" },
  { to: "/activity", label: "Activity" },
  { to: "/compare", label: "Compare" },
  { to: "/chat", label: "Chat" },
];

export function NavBar() {
  return (
    <nav className="flex items-center gap-1 text-sm overflow-x-auto">
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          className={({ isActive }) =>
            cn(
              "shrink-0 relative px-3 py-1.5 rounded-md text-text-muted transition-colors",
              "hover:text-text hover:bg-white/[0.04]",
              isActive && "text-text bg-white/[0.06]"
            )
          }
        >
          {it.label}
        </NavLink>
      ))}
    </nav>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes.tsx frontend/src/layout/NavBar.tsx
git commit -m "Wire new feature routes and expand nav bar"
```

---

## Task 12: Scroll reveal primitive + apply to grids

**Files:**
- Modify: `frontend/package.json` (add dep)
- Create: `frontend/src/design/ScrollReveal.tsx`
- Modify: `frontend/src/features/discover/AnimeGrid.tsx`

- [ ] **Step 1: Add `react-intersection-observer`**

```bash
cd frontend && npm install react-intersection-observer@^9.13.1
```

Expected: `added 1 package`.

- [ ] **Step 2: Create `frontend/src/design/ScrollReveal.tsx`**

```tsx
import { motion } from "framer-motion";
import { useInView } from "react-intersection-observer";
import type { ReactNode } from "react";
import { transitions } from "./motion";

interface Props {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}

export function ScrollReveal({ children, delay = 0, y = 14, className }: Props) {
  const { ref, inView } = useInView({ threshold: 0.1, triggerOnce: true });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y }}
      transition={{ ...transitions.ease, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 3: Wrap AnimeGrid items in ScrollReveal (stagger 0.03s)**

Open `frontend/src/features/discover/AnimeGrid.tsx`. Replace the grid render with:

```tsx
// existing imports, plus
import { ScrollReveal } from "@/design/ScrollReveal";

// ... in the return when anime.length > 0:
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
      {anime.map((a, i) => (
        <ScrollReveal key={a.id} delay={Math.min(i, 14) * 0.03}>
          <AnimeCard anime={a} index={0} />
        </ScrollReveal>
      ))}
    </div>
  );
```

The change to `AnimeGrid` file (full replacement):

```tsx
import type { AnimeSummary } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { ScrollReveal } from "@/design/ScrollReveal";
import { AnimeCard } from "./AnimeCard";

interface Props {
  anime: AnimeSummary[];
  loading?: boolean;
  empty?: React.ReactNode;
}

export function AnimeGrid({ anime, loading, empty }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="aspect-[2/3]" rounded="lg" />
            <Skeleton className="h-3 mt-2 w-3/4" />
          </div>
        ))}
      </div>
    );
  }
  if (!anime.length) {
    return (
      <div className="py-24 text-center text-text-muted">
        {empty ?? "No anime found."}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
      {anime.map((a, i) => (
        <ScrollReveal key={a.id} delay={Math.min(i, 14) * 0.03}>
          <AnimeCard anime={a} index={0} />
        </ScrollReveal>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/design/ScrollReveal.tsx frontend/src/features/discover/AnimeGrid.tsx
git commit -m "Add ScrollReveal primitive and apply staggered reveal to anime grid"
```

---

## Task 13: Code-split routes with React.lazy

**Files:**
- Modify: `frontend/src/routes.tsx`
- Create: `frontend/src/layout/RouteSkeleton.tsx`

- [ ] **Step 1: Create `frontend/src/layout/RouteSkeleton.tsx`**

```tsx
import { Skeleton } from "@/design/Skeleton";

export function RouteSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-12 w-64" rounded="lg" />
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3]" rounded="lg" />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Replace `frontend/src/routes.tsx` with lazy loading**

```tsx
import { Suspense, lazy } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";
import { RouteSkeleton } from "@/layout/RouteSkeleton";
import { LandingPage } from "@/features/landing/LandingPage";

const AuthPage = lazy(() =>
  import("@/features/auth/AuthPage").then((m) => ({ default: m.AuthPage }))
);
const DiscoverPage = lazy(() =>
  import("@/features/discover/DiscoverPage").then((m) => ({ default: m.DiscoverPage }))
);
const AnimeDetailPage = lazy(() =>
  import("@/features/details/AnimeDetailPage").then((m) => ({ default: m.AnimeDetailPage }))
);
const WatchlistPage = lazy(() =>
  import("@/features/watchlist/WatchlistPage").then((m) => ({ default: m.WatchlistPage }))
);
const ForYouPage = lazy(() =>
  import("@/features/for-you/ForYouPage").then((m) => ({ default: m.ForYouPage }))
);
const ChatPage = lazy(() =>
  import("@/features/chat/ChatPage").then((m) => ({ default: m.ChatPage }))
);
const CollectionsListPage = lazy(() =>
  import("@/features/collections/CollectionsListPage").then((m) => ({
    default: m.CollectionsListPage,
  }))
);
const CollectionDetailPage = lazy(() =>
  import("@/features/collections/CollectionDetailPage").then((m) => ({
    default: m.CollectionDetailPage,
  }))
);
const StatsPage = lazy(() =>
  import("@/features/stats/StatsPage").then((m) => ({ default: m.StatsPage }))
);
const SeasonalPage = lazy(() =>
  import("@/features/seasonal/SeasonalPage").then((m) => ({ default: m.SeasonalPage }))
);
const ActivityPage = lazy(() =>
  import("@/features/activity/ActivityPage").then((m) => ({ default: m.ActivityPage }))
);
const ComparePage = lazy(() =>
  import("@/features/compare/ComparePage").then((m) => ({ default: m.ComparePage }))
);

const withSuspense = (node: React.ReactNode) => (
  <Suspense fallback={<RouteSkeleton />}>{node}</Suspense>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "auth", element: withSuspense(<AuthPage />) },
      { path: "discover", element: withSuspense(<DiscoverPage />) },
      { path: "anime/:id", element: withSuspense(<AnimeDetailPage />) },
      { path: "watchlist", element: withSuspense(<WatchlistPage />) },
      { path: "for-you", element: withSuspense(<ForYouPage />) },
      { path: "chat", element: withSuspense(<ChatPage />) },
      { path: "collections", element: withSuspense(<CollectionsListPage />) },
      { path: "collections/:id", element: withSuspense(<CollectionDetailPage />) },
      { path: "stats", element: withSuspense(<StatsPage />) },
      { path: "seasonal", element: withSuspense(<SeasonalPage />) },
      { path: "activity", element: withSuspense(<ActivityPage />) },
      { path: "compare", element: withSuspense(<ComparePage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
```

- [ ] **Step 3: Verify build produces multiple chunks**

```bash
cd frontend && npm run build
ls -la dist/assets/*.js | wc -l
```

Expected: ≥5 JS files (one main bundle + multiple lazy chunks).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes.tsx frontend/src/layout/RouteSkeleton.tsx
git commit -m "Code-split route modules with React.lazy and Suspense fallback"
```

---

## Task 14: Image polish — blur-up placeholders for anime cards

**Files:**
- Modify: `frontend/src/features/discover/AnimeCard.tsx`

- [ ] **Step 1: Replace `frontend/src/features/discover/AnimeCard.tsx` with blur-up support**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { AnimeSummary } from "@/types/models";
import { Badge } from "@/design/Badge";
import { cn } from "@/lib/cn";
import { genreColor } from "@/lib/genres";
import { transitions } from "@/design/motion";

interface Props {
  anime: AnimeSummary;
  index?: number;
  compact?: boolean;
}

export function AnimeCard({ anime, index = 0, compact }: Props) {
  const [loaded, setLoaded] = useState(false);
  const score = anime.community_score ?? anime.api_score;
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g: { name?: string } | string) =>
      typeof g === "string" ? g : g.name ?? ""
    )
    .filter(Boolean)
    .slice(0, 3);
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...transitions.ease, delay: Math.min(index, 10) * 0.02 }}
    >
      <Link
        to={`/anime/${anime.id}`}
        className={cn(
          "group block rounded-lg overflow-hidden border border-border",
          "bg-surface hover:border-border-strong transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50"
        )}
      >
        <div
          className={cn(
            "relative bg-black/40 overflow-hidden",
            compact ? "aspect-[3/4]" : "aspect-[2/3]"
          )}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-white/[0.04] to-black/20" />
          {anime.image_url ? (
            <img
              src={anime.image_url}
              alt={anime.title}
              loading="lazy"
              onLoad={() => setLoaded(true)}
              className={cn(
                "relative w-full h-full object-cover transition-all duration-500",
                "group-hover:scale-[1.04]",
                loaded ? "opacity-100 blur-0" : "opacity-0 blur-md"
              )}
            />
          ) : (
            <div className="relative w-full h-full flex items-center justify-center text-text-dim text-xs">
              No image
            </div>
          )}
          {score ? (
            <span className="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur-md text-xs font-mono text-amber">
              {Number(score).toFixed(1)}
            </span>
          ) : null}
        </div>
        <div className="p-3">
          <h3 className="text-sm font-semibold line-clamp-2 mb-1.5">
            {anime.title_english ?? anime.title}
          </h3>
          <div className="flex flex-wrap gap-1">
            {genres.map((g) => (
              <Badge key={g} color={genreColor(g)}>
                {g}
              </Badge>
            ))}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/discover/AnimeCard.tsx
git commit -m "Add blur-up placeholder and smoother image reveal on anime cards"
```

---

## Task 15: render.yaml, .env.example polish, archive legacy frontend

**Files:**
- Modify: `render.yaml`
- Modify: `.env.example`
- Move: `static/index.html` → `legacy/index.html.bak`
- Create: `static/.gitkeep`

- [ ] **Step 1: Replace `render.yaml` with both-provider config**

```yaml
services:
  - type: web
    name: bingery
    env: python
    buildCommand: "./build.sh"
    startCommand: "gunicorn app:app --workers 2 --timeout 120"
    healthCheckPath: /api/health
    envVars:
      - key: PYTHON_VERSION
        value: "3.12.3"
      - key: AI_PROVIDER
        value: anthropic
      - key: ANTHROPIC_MODEL
        value: claude-sonnet-4-6
      - key: OLLAMA_MODEL
        value: gemma4:31b
      - key: OLLAMA_BASE_URL
        value: http://localhost:11434
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: bingery-db
          property: connectionString
databases:
  - name: bingery-db
    plan: free
```

- [ ] **Step 2: Update `.env.example` with the hybrid-provider variables**

Overwrite `.env.example` with:

```
# ── Runtime provider ──────────────────────────────────────────────────────
AI_PROVIDER=ollama            # ollama | anthropic

# Anthropic (cloud) — required when AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6

# Ollama (local) — required when AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:31b

# ── Flask / DB ────────────────────────────────────────────────────────────
DATABASE_URL=sqlite:///bingery.db
JWT_SECRET_KEY=change-me

# Frontend dev server only (see frontend/.env.example)
```

- [ ] **Step 3: Archive `static/index.html`**

```bash
mkdir -p legacy
git mv static/index.html legacy/index.html.bak
touch static/.gitkeep
git add static/.gitkeep
```

- [ ] **Step 4: Verify Flask still boots with the new static_folder fallback**

```bash
python -m flask --app app run --port 5000 &
sleep 3
curl -sI http://127.0.0.1:5000/api/health | head -1
curl -sI http://127.0.0.1:5000/ | head -1
kill %1 2>/dev/null || true
```

Expected: both `HTTP/1.1 200 OK` (the catch-all serves `frontend/dist/index.html` after Plan 2 Task 20's build; otherwise serves `static/.gitkeep` path — which returns index by SPA rule).

If the second call 404s because `dist/` doesn't exist yet on this machine, run `cd frontend && npm run build` and retry.

- [ ] **Step 5: Commit**

```bash
git add render.yaml .env.example legacy/index.html.bak static/.gitkeep
git commit -m "Update deploy config, archive legacy frontend, document env vars"
```

---

## Task 16: Full-flow Playwright e2e

**Files:**
- Create: `frontend/e2e/full-flow.spec.ts`
- Modify: `frontend/e2e/smoke.spec.ts`

- [ ] **Step 1: Extend smoke spec with new routes**

Replace `frontend/e2e/smoke.spec.ts` with:

```ts
import { test, expect } from "@playwright/test";

test("landing renders hero and nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Discover what/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Discover" })).toBeVisible();
});

test("discover loads grid", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
});

test("seasonal page loads", async ({ page }) => {
  await page.goto("/seasonal");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("collections shows sign-in gate when logged out", async ({ page }) => {
  await page.goto("/collections");
  await expect(
    page.getByRole("heading", { name: /Sign in to build/i })
  ).toBeVisible();
});

test("stats shows sign-in gate when logged out", async ({ page }) => {
  await page.goto("/stats");
  await expect(
    page.getByRole("heading", { name: /Sign in for your stats/i })
  ).toBeVisible();
});

test("404 path navigates to landing", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
});
```

- [ ] **Step 2: Create `frontend/e2e/full-flow.spec.ts`**

```ts
import { test, expect } from "@playwright/test";

test("register → discover → detail navigation", async ({ page }) => {
  const suffix = Date.now();
  await page.goto("/auth");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("Username").fill(`e2e${suffix}`);
  await page.getByLabel("Email").fill(`e2e${suffix}@test.local`);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/discover/);

  const firstCard = page.getByRole("link").filter({ hasText: /./ }).first();
  if (await firstCard.count()) {
    await firstCard.click();
    await expect(page).toHaveURL(/\/anime\//);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  }
});
```

- [ ] **Step 3: Run the suite**

```bash
cd frontend && npx playwright test
```

Expected: 7 passing (6 smoke + 1 full-flow). The full-flow test may skip the detail click if the seed DB is empty — it still passes because of the guard.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/smoke.spec.ts frontend/e2e/full-flow.spec.ts
git commit -m "Expand Playwright smoke and add register-to-detail full flow"
```

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-04-17-bingery-revamp-design.md`):

| Spec section | Covered in |
|---|---|
| New feature A — Stats | Tasks 6, 7 |
| New feature B — Collections | Tasks 1, 2, 3, 4, 5 |
| New feature C — Seasonal | Task 8 |
| New feature D — Activity timeline | Task 9 |
| New feature E — Compare | Task 10 |
| Premium motion on buttons | Plan 2 Task 6 (Button) + Plan 2 Task 19 (page transitions) |
| Scroll reveals | Task 12 |
| Performance (code split) | Task 13 |
| Image polish (blur-up) | Task 14 |
| Deploy (Render, both providers) | Task 15 |
| Legacy cleanup | Task 15 |
| Testing pyramid | Task 16 (e2e) — Vitest unit coverage from Plan 2 |
| AI-attribution clean commits | Every task |

**2. Placeholder scan**: No TBD/TODO. Every file replacement and addition has complete code. Env vars are fully enumerated.

**3. Type consistency**:
- `Season` union `"winter" | "spring" | "summer" | "fall"` consistent across models, SeasonPicker, SeasonalPage, and hook.
- `ActivityKind` union matches switch arms in `ActivityEntry`.
- `StatsOverview.avg_rating` is `number | null` — guarded in `OverviewCards`.
- `CompareTaste.score_agreement` is a fraction (0..1) — rendered as percent in `TasteVenn`.
- `CollectionDetail.owner` shape matches usage in `CollectionDetailPage`.
- `useAddToCollection` / `useRemoveFromCollection` signatures align with `api.addToCollection` / `api.removeFromCollection`.

**4. Scope check**: 16 tasks, each independently verifiable; the plan finishes with green e2e and a deployable artifact. The trilogy (Plans 1 → 2 → 3) produces the full revamp, with each plan producing working, shippable software on its own.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-plan-3-features-polish-deploy.md`.

Three-plan arc now fully written:

1. **Plan 1** — [backend foundation](./2026-04-17-plan-1-backend-foundation.md) (18 tasks)
2. **Plan 2** — [frontend foundation](./2026-04-17-plan-2-frontend-foundation.md) (20 tasks)
3. **Plan 3** — features, polish, deploy (this file, 16 tasks)

Two execution options:

- **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
- **Inline Execution** — tasks executed in this session with checkpoint reviews.

Plans 1 → 2 → 3 should run in order since Plan 2 depends on Plan 1's Collections/Stats/Seasonal/Activity/Compare endpoints for type checks, and Plan 3 depends on Plan 2's design primitives and hooks.
