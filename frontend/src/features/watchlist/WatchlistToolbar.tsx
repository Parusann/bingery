import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Star, X } from "lucide-react";
import type { WatchlistSort, GenreMatchMode, ViewMode } from "@/types/models";
import { cn } from "@/lib/cn";
import { transitions } from "@/design/motion";

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

// System field skin — same warm focus treatment as design/Input.
const fieldClass =
  "rounded-lg border border-border bg-surface text-sm outline-none transition-colors " +
  "focus:border-amber/50 focus:ring-1 focus:ring-amber/35 focus:bg-amber/[0.03]";

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
  // Genre filter lives in a popover: dozens of options would clutter a flat
  // rail, so at rest only the SELECTED genres render (as removable chips).
  const [genresOpen, setGenresOpen] = useState(false);
  const popRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!genresOpen) return;
    const onDown = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) {
        setGenresOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setGenresOpen(false);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [genresOpen]);

  const toggleGenre = (g: string, on: boolean) =>
    onChange({ genres: on ? genres.filter((x) => x !== g) : [...genres, g] });

  return (
    <div className="mb-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => onChange({ q: e.target.value })}
          placeholder="Search your watchlist"
          aria-label="Search your watchlist"
          className={cn(
            fieldClass,
            "min-w-[180px] flex-1 h-11 px-3.5 placeholder:text-text-dim"
          )}
        />
        <select
          value={sort}
          onChange={(e) => onChange({ sort: e.target.value as WatchlistSort })}
          aria-label="Sort"
          className={cn(fieldClass, "h-11 px-3")}
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
            "inline-flex items-center gap-1.5 rounded-lg border h-11 px-3.5 text-sm transition-colors",
            favoritesOnly
              ? "border-gold-bd bg-gold/[0.08] text-gold"
              : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
          )}
        >
          <Star
            className="h-3.5 w-3.5"
            fill={favoritesOnly ? "currentColor" : "none"}
            aria-hidden
          />
          Favorites
        </button>
        <div
          role="group"
          aria-label="View mode"
          className="inline-flex overflow-hidden rounded-lg border border-border bg-surface p-1 gap-0.5"
        >
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => onChange({ view: v.key })}
              aria-pressed={view === v.key}
              className={cn(
                "px-3 min-h-[36px] rounded-sm text-caption transition-colors",
                view === v.key
                  ? "bg-surface-strong text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                  : "text-text-muted hover:text-text"
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {genreOptions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <div ref={popRef} className="relative">
            <button
              type="button"
              onClick={() => setGenresOpen((o) => !o)}
              aria-expanded={genresOpen}
              aria-haspopup="true"
              className={cn(
                "inline-flex items-center gap-1.5 rounded-pill border px-3.5 py-1.5 min-h-[36px] text-xs transition-colors",
                genres.length > 0
                  ? "border-amber/60 bg-amber/10 text-amber"
                  : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
              )}
            >
              Genres
              {genres.length > 0 ? (
                <span className="font-mono tnum text-[10px] px-1.5 py-px rounded-pill bg-amber/15">
                  {genres.length}
                </span>
              ) : null}
              <ChevronDown
                className={cn("h-3.5 w-3.5 transition-transform", genresOpen && "rotate-180")}
                aria-hidden
              />
            </button>
            <AnimatePresence>
              {genresOpen ? (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={transitions.easeFast}
                  className="absolute left-0 top-full mt-2 z-30 w-[min(420px,calc(100vw-2rem))] rounded-lg border border-border-strong bg-bg-elevated/95 backdrop-blur-xl shadow-e3 p-3"
                >
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    <span className="font-mono text-micro uppercase text-text-dim">
                      Filter by genre
                    </span>
                    <div className="flex items-center gap-2">
                      {genres.length > 1 ? (
                        <button
                          type="button"
                          onClick={() =>
                            onChange({ genreMode: genreMode === "any" ? "all" : "any" })
                          }
                          title="Match anime that have any vs all of the selected genres"
                          className="rounded-pill border border-border bg-surface px-2.5 py-1 text-[11px] font-mono text-text-muted transition-colors hover:text-text hover:border-border-strong"
                        >
                          Match: {genreMode === "any" ? "Any" : "All"}
                        </button>
                      ) : null}
                      {genres.length > 0 ? (
                        <button
                          type="button"
                          onClick={() => onChange({ genres: [] })}
                          className="text-[11px] font-mono text-text-dim transition-colors hover:text-danger"
                        >
                          Clear
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5 max-h-56 overflow-y-auto pr-1">
                    {genreOptions.map((g) => {
                      const on = genres.includes(g);
                      return (
                        <button
                          key={g}
                          type="button"
                          onClick={() => toggleGenre(g, on)}
                          aria-pressed={on}
                          className={cn(
                            "rounded-pill border px-3 py-1.5 text-xs transition-colors",
                            on
                              ? "border-amber/60 bg-amber/10 text-amber"
                              : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
                          )}
                        >
                          {g}
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>

          {/* Selected genres — removable chips, the only ones shown at rest */}
          {genres.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => toggleGenre(g, true)}
              aria-label={`Remove ${g} filter`}
              className="inline-flex items-center gap-1 rounded-pill border border-amber/60 bg-amber/10 px-3 py-1.5 text-xs text-amber transition-colors hover:border-amber hover:bg-amber/[0.16]"
            >
              {g}
              <X className="h-3 w-3" aria-hidden />
            </button>
          ))}
          {genres.length > 1 ? (
            <span className="font-mono text-[11px] text-text-dim">
              match {genreMode === "any" ? "any" : "all"}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
