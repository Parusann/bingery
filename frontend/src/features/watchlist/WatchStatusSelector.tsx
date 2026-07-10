import { useEffect, useState } from "react";
import { Star } from "lucide-react";
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
 * Watchlist status as inline pills + a labelled Favorite toggle.
 *
 * Selection is optimistic: clicking a pill highlights it immediately (instead
 * of waiting on the server round-trip, which previously gave no visible
 * response), then fires the mutation. If the save fails we revert to the
 * server value; `current`/`isFavorite` re-sync the local state once the
 * detail query refetches.
 *
 * Favorite reads GOLD — the palette's reserved star color.
 */
export function WatchStatusSelector({ animeId, current, isFavorite }: Props) {
  const setStatus = useSetWatchStatus();
  const toggleFav = useToggleFavorite();
  const remove = useRemoveFromWatchlist();

  const [selected, setSelected] = useState<WatchStatus | null>(current);
  const [fav, setFav] = useState(isFavorite);
  useEffect(() => setSelected(current), [current]);
  useEffect(() => setFav(isFavorite), [isFavorite]);

  const pick = (key: WatchStatus) => {
    if (key === selected) {
      setSelected(null);
      remove.mutate(animeId, { onError: () => setSelected(current) });
    } else {
      setSelected(key);
      setStatus.mutate(
        { animeId, status: key },
        { onError: () => setSelected(current) }
      );
    }
  };

  const onFav = () => {
    setFav((f) => !f);
    toggleFav.mutate(animeId, { onError: () => setFav(isFavorite) });
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {STATUSES.map((s) => {
        const active = selected === s.key;
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
              "px-3 py-1 min-h-[32px] rounded-pill text-xs border transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
              active
                ? "border-transparent text-bg font-medium shadow-sm"
                : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
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
        onClick={onFav}
        aria-pressed={fav}
        aria-label={fav ? "Remove from favorites" : "Add to favorites"}
        title={fav ? "Favorited — click to unfavorite" : "Add to favorites"}
        className={cn(
          "inline-flex items-center gap-1.5 px-3 py-1 min-h-[32px] rounded-pill text-xs border transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
          fav
            ? "border-gold-bd bg-gold/[0.08] text-gold"
            : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
        )}
      >
        <Star
          className="h-3 w-3"
          fill={fav ? "currentColor" : "none"}
          aria-hidden
        />
        {fav ? "Favorited" : "Favorite"}
      </button>
    </div>
  );
}
