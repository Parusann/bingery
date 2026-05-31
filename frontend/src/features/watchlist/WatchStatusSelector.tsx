import type { WatchStatus } from "@/types/models";
import { STATUSES } from "./StatusTabs";
import { cn } from "@/lib/cn";
import {
  useRemoveFromWatchlist,
  useSetWatchStatus,
  useToggleFavorite,
} from "@/hooks/useWatchlist";

interface Props {
  animeId: number;
  current: WatchStatus | null;
  isFavorite: boolean;
}

/**
 * Watchlist status shown as inline pills: one click sets the status, clicking
 * the already-active pill removes the anime from the list. Rating an anime
 * elsewhere still auto-sets "Completed" — these pills are for setting status
 * directly (e.g. Plan to Watch / Watching) without rating. The Favorite toggle
 * sits beside them with a visible label so its purpose is obvious.
 */
export function WatchStatusSelector({ animeId, current, isFavorite }: Props) {
  const setStatus = useSetWatchStatus();
  const toggleFav = useToggleFavorite();
  const remove = useRemoveFromWatchlist();

  const pick = (key: WatchStatus) => {
    if (key === current) remove.mutate(animeId);
    else setStatus.mutate({ animeId, status: key });
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {STATUSES.map((s) => {
        const active = current === s.key;
        return (
          <button
            key={s.key}
            type="button"
            onClick={() => pick(s.key)}
            aria-pressed={active}
            title={
              active
                ? `${s.label} — click to remove from watchlist`
                : `Mark as ${s.label}`
            }
            className={cn(
              "px-3 py-1 rounded-full text-xs border transition-colors",
              active
                ? "border-transparent text-bg font-medium"
                : "border-border text-text-muted hover:text-text hover:border-border-strong"
            )}
            style={active ? { background: s.color } : undefined}
          >
            {s.label}
          </button>
        );
      })}

      <span className="mx-0.5 h-4 w-px bg-border" aria-hidden="true" />

      <button
        type="button"
        onClick={() => toggleFav.mutate(animeId)}
        aria-pressed={isFavorite}
        aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
        title={isFavorite ? "Favorited — click to unfavorite" : "Add to favorites"}
        className={cn(
          "inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs border transition-colors",
          isFavorite
            ? "border-amber text-amber"
            : "border-border text-text-muted hover:text-text hover:border-border-strong"
        )}
        style={isFavorite ? { background: "rgba(230,166,128,0.12)" } : undefined}
      >
        <span aria-hidden="true">{isFavorite ? "★" : "☆"}</span>
        {isFavorite ? "Favorited" : "Favorite"}
      </button>
    </div>
  );
}
