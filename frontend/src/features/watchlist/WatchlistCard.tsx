import { Link } from "react-router-dom";
import { Star } from "lucide-react";
import type { WatchEntry } from "@/types/models";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

/**
 * Watchlist tile: the anime poster plus the two things you personally gave it —
 * your rating (score out of 10) and the fan-genres you assigned. Links through
 * to the detail page. `compact` shrinks padding and hides the genre row for a
 * denser grid. Shares the Discover card's hover language; your score reads
 * gold (the reserved star color).
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
      className="group block overflow-hidden rounded-lg border border-border bg-surface transition-all duration-base ease-out hover:border-amber/35 hover:-translate-y-1 hover:shadow-e2 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
    >
      <div className="relative aspect-[2/3] overflow-hidden bg-black/40">
        {a.image_url ? (
          <img
            src={a.image_url}
            alt={a.title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-slow ease-out group-hover:scale-[1.05]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-text-dim">
            No image
          </div>
        )}
        {entry.score != null ? (
          <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md bg-bg/70 border border-gold-bd px-2 py-0.5 font-mono text-xs tnum text-gold backdrop-blur-md">
            <Star className="h-3 w-3" fill="currentColor" aria-hidden />
            {entry.score}/10
          </span>
        ) : (
          <span className="absolute right-2 top-2 rounded-md bg-bg/60 border border-border px-2 py-0.5 font-mono text-[10px] text-text-dim backdrop-blur-md">
            unrated
          </span>
        )}
      </div>
      <div className={compact ? "p-2" : "p-3"}>
        <h3
          className={
            compact
              ? "line-clamp-2 text-xs font-medium leading-snug"
              : "mb-1.5 line-clamp-2 text-sm font-medium leading-snug"
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
                <span className="self-center font-mono text-[10px] tnum text-text-dim">
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
