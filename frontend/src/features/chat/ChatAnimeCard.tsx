import { Link } from "react-router-dom";
import type { ChatAnimeRef } from "@/types/models";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

export function ChatAnimeCard({ anime }: { anime: ChatAnimeRef }) {
  const inner = (
    <div className="flex gap-3 p-3 rounded-lg border border-border bg-surface hover:border-border-strong transition-colors">
      {anime.image_url ? (
        <img
          src={anime.image_url}
          alt=""
          className="w-12 h-16 object-cover rounded"
        />
      ) : (
        <div className="w-12 h-16 rounded bg-white/5" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold truncate">{anime.title}</div>
        {anime.genres?.length ? (
          <div className="flex gap-1 flex-wrap mt-1.5">
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
