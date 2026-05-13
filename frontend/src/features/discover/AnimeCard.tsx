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
