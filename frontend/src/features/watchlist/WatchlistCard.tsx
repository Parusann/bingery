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
