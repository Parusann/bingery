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
