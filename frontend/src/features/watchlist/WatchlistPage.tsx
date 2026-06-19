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
