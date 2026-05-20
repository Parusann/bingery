import { Link } from "react-router-dom";
import type { ChatAnimeRef } from "@/types/models";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

export function ChatAnimeCard({ anime }: { anime: ChatAnimeRef }) {
  const inner = (
    <div className="group flex gap-3.5 p-3 rounded-xl border border-amber/20 bg-white/[0.04] backdrop-blur-md hover:border-amber/55 hover:bg-amber/[0.06] hover:-translate-y-px transition-all duration-200 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.5)]">
      {anime.image_url ? (
        <img
          src={anime.image_url}
          alt=""
          loading="lazy"
          className="w-14 h-20 object-cover rounded-md border border-border shrink-0 group-hover:border-amber/40 transition-colors"
        />
      ) : (
        <div className="w-14 h-20 rounded-md bg-white/[0.05] border border-border shrink-0" />
      )}
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <div className="text-sm font-display leading-snug line-clamp-2 group-hover:text-amber transition-colors">
          {anime.title}
        </div>
        {anime.year ? (
          <div className="font-mono text-[10px] tracking-wider uppercase text-text-dim">
            {anime.year}
          </div>
        ) : null}
        {anime.genres?.length ? (
          <div className="flex gap-1 flex-wrap mt-auto">
            {anime.genres.slice(0, 3).map((g) => (
              <Badge key={g} color={genreColor(g)}>
                {g}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
  return anime.id ? (
    <Link to={`/anime/${anime.id}`} className="block">
      {inner}
    </Link>
  ) : (
    inner
  );
}
