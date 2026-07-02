import { useState } from "react";
import { Link } from "react-router-dom";
import type { AnimeSummary } from "@/types/models";
import { Badge } from "@/design/Badge";
import { cn } from "@/lib/cn";
import { genreColor } from "@/lib/genres";

interface Props {
  anime: AnimeSummary;
  index?: number; // kept for API compatibility; entrances are owned by the grid
  compact?: boolean;
}

// The grid (ScrollReveal) owns the entrance — the card only handles
// hover/press, so cards never double-animate. Hover is the signature:
// a quiet lift, warm border, slow poster zoom, and a scrim that lets the
// title glow amber.
export function AnimeCard({ anime, compact }: Props) {
  const [loaded, setLoaded] = useState(false);
  const score = anime.community_score ?? anime.api_score;
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g: { name?: string } | string) =>
      typeof g === "string" ? g : g.name ?? ""
    )
    .filter(Boolean)
    .slice(0, 3);
  return (
    <Link
      to={`/anime/${anime.id}`}
      className={cn(
        "group relative block overflow-hidden rounded-lg border border-border bg-surface",
        "transition-all duration-base ease-out",
        "hover:border-amber/35 hover:-translate-y-1 hover:shadow-e2",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
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
              "relative w-full h-full object-cover transition-all duration-slow ease-out",
              "group-hover:scale-[1.05]",
              loaded ? "opacity-100 blur-0" : "opacity-0 blur-md"
            )}
          />
        ) : (
          <div className="relative w-full h-full flex items-center justify-center text-text-dim text-xs">
            No image
          </div>
        )}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-base"
        />
        {score ? (
          <span className="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-bg/70 backdrop-blur-md border border-amber/25 text-xs font-mono tnum text-amber-hi">
            {Number(score).toFixed(1)}
          </span>
        ) : null}
      </div>
      <div className="p-2.5 sm:p-3">
        <h3 className="text-xs sm:text-sm font-medium leading-snug line-clamp-2 mb-1.5 transition-colors duration-base group-hover:text-amber-hi">
          {anime.title_english ?? anime.title}
        </h3>
        <div className="flex flex-wrap gap-1">
          {genres.map((g, i) => (
            <span
              key={g}
              className={i >= 2 ? "hidden sm:inline-flex" : "inline-flex"}
            >
              <Badge color={genreColor(g)}>{g}</Badge>
            </span>
          ))}
        </div>
      </div>
    </Link>
  );
}
