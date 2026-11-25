import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
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
  watched: number;
  total: number | null;
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
export function WatchStatusSelector({ animeId, current, isFavorite, watched, total }: Props) {
  const setStatus = useSetWatchStatus();
  const toggleFav = useToggleFavorite();
  const remove = useRemoveFromWatchlist();

  const [selected, setSelected] = useState<WatchStatus | null>(current);
  const [fav, setFav] = useState(isFavorite);
  const [draft, setDraft] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const submitting = useRef(false);
  useEffect(() => setSelected(current), [current]);
  useEffect(() => setFav(isFavorite), [isFavorite]);

  const busy = setStatus.isPending || toggleFav.isPending || remove.isPending;
  const failure = setStatus.error || toggleFav.error || remove.error;
  const count = Number(draft ?? watched);
  const limit = total && total > 0 ? total : undefined;
  const valid = draft !== "" && Number.isSafeInteger(count) && count >= 0 &&
    (limit === undefined || count <= limit);

  function saveProgress(event: FormEvent) {
    event.preventDefault();
    if (!current || selected !== current || !valid || count === watched || busy || submitting.current) return;
    submitting.current = true;
    setStatus.mutate({ animeId, status: current, episodesWatched: count }, {
      onSuccess: () => { setDraft(null); setSaved(true); },
      onSettled: () => { submitting.current = false; },
    });
  }

  const pick = (key: WatchStatus) => {
    setSaved(false);
    if (key === selected) {
      setSelected(null);
      remove.mutate(animeId, {
        onSuccess: () => setDraft(null),
        onError: () => setSelected(current),
      });
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
            disabled={busy}
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
        disabled={busy}
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
      {current && selected && (
        <form onSubmit={saveProgress} className="mt-1 flex w-full flex-wrap items-center gap-2 text-sm">
          <label className="flex items-center gap-2 text-text-muted">
            Episodes watched
            <input
              type="number" min={0} max={limit ?? Number.MAX_SAFE_INTEGER} step={1}
              inputMode="numeric" required disabled={busy || selected !== current}
              value={draft ?? watched}
              onChange={(event) => { setDraft(event.target.value); setSaved(false); }}
              aria-invalid={draft !== null && !valid}
              aria-describedby={draft !== null && !valid ? "episode-count-help" : undefined}
              className="h-10 w-20 rounded-md border border-border bg-bg/70 px-2 font-mono text-text"
            />
          </label>
          {limit !== undefined && <span className="text-text-muted">of {limit}</span>}
          <button type="submit" disabled={busy || selected !== current || !valid || count === watched}
            className="h-10 rounded-pill border border-amber/40 px-3 text-xs font-medium text-amber hover:bg-amber/10 disabled:opacity-50">
            Save progress
          </button>
          {saved && <span role="status" className="text-xs text-success">Progress saved</span>}
          {draft !== null && !valid && <p id="episode-count-help" className="w-full text-xs text-danger">
            {limit !== undefined ? `Enter a whole number from 0 to ${limit}.` : "Enter a non-negative whole number."}
          </p>}
        </form>
      )}
      {failure && <p role="alert" className="w-full text-sm text-danger">{failure.message}</p>}
    </div>
  );
}
