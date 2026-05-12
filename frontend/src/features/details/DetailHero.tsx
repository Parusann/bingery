import type { AnimeDetail } from "@/types/models";
import { LiquidGLSurface } from "@/design/LiquidGLSurface";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

export function DetailHero({ anime }: { anime: AnimeDetail }) {
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g) => (typeof g === "string" ? g : g.name))
    .filter(Boolean) as string[];
  return (
    <div className="relative overflow-hidden rounded-xl mb-6">
      {anime.banner_url ? (
        <img
          src={anime.banner_url}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
      ) : null}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/80 to-transparent" />
      <LiquidGLSurface className="relative z-10 p-6 md:p-10 flex flex-col md:flex-row gap-6">
        {anime.image_url ? (
          <img
            src={anime.image_url}
            alt=""
            className="w-40 md:w-56 aspect-[2/3] rounded-lg object-cover shrink-0 shadow-2xl"
          />
        ) : null}
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-4xl md:text-5xl mb-2">
            {anime.title_english ?? anime.title}
          </h1>
          {anime.title_english && anime.title !== anime.title_english ? (
            <p className="text-text-muted mb-3">{anime.title}</p>
          ) : null}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {genres.slice(0, 6).map((g) => (
              <Badge key={g} color={genreColor(g)}>
                {g}
              </Badge>
            ))}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Stat label="Episodes" value={anime.episodes ?? "—"} />
            <Stat label="Year" value={anime.year ?? "—"} />
            <Stat label="Format" value={anime.format ?? "—"} />
            <Stat label="Score" value={anime.api_score?.toFixed(1) ?? "—"} />
          </div>
          {anime.description ? (
            <p className="mt-5 text-text-muted leading-relaxed max-w-3xl">
              {anime.description.replace(/<[^>]+>/g, "")}
            </p>
          ) : null}
        </div>
      </LiquidGLSurface>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs text-text-dim uppercase tracking-wider">{label}</div>
      <div className="text-lg font-mono text-amber">{value}</div>
    </div>
  );
}
