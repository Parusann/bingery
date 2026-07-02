import type { ReactNode } from "react";
import type { AnimeDetail } from "@/types/models";
import { LiquidGLSurface } from "@/design/LiquidGLSurface";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

interface HeroProps {
  anime: AnimeDetail;
  actions?: ReactNode;
}

// The signature surface: banner art washed warm and vignetted toward the
// stage, poster lifted to e3, display-serif title with the native title as
// an italic underline. Score is the only amber number.
export function DetailHero({ anime, actions }: HeroProps) {
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g) => (typeof g === "string" ? g : g.name))
    .filter(Boolean) as string[];
  return (
    <div className="relative overflow-hidden rounded-xl mb-6">
      {anime.banner_url ? (
        <img
          src={anime.banner_url}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-30 scale-105"
        />
      ) : null}
      {/* stage vignette + warm wash over the banner */}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/75 to-bg/25" />
      <div className="absolute inset-0 bg-gradient-to-r from-bg/60 via-transparent to-transparent" />
      <div className="absolute inset-0 bg-amber/[0.04] mix-blend-overlay" />
      <LiquidGLSurface className="relative z-10 p-4 sm:p-6 md:p-10 flex flex-col md:flex-row gap-6 md:gap-8">
        {anime.image_url ? (
          <img
            src={anime.image_url}
            alt=""
            className="w-40 md:w-56 aspect-[2/3] rounded-lg object-cover shrink-0 shadow-e3 ring-1 ring-white/10"
          />
        ) : null}
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-display-hero mb-2">
            {anime.title_english ?? anime.title}
          </h1>
          {anime.title_english && anime.title !== anime.title_english ? (
            <p className="font-display italic text-body-lg text-text-muted mb-3">
              {anime.title}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <div className="flex flex-wrap gap-1.5">
              {genres.slice(0, 6).map((g) => (
                <Badge key={g} color={genreColor(g)}>
                  {g}
                </Badge>
              ))}
            </div>
            {actions ? (
              <div className="ml-auto flex flex-wrap gap-2">{actions}</div>
            ) : null}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-xl">
            <Stat label="Episodes" value={anime.episodes ?? "—"} />
            <Stat label="Year" value={anime.year ?? "—"} />
            <Stat label="Format" value={anime.format ?? "—"} />
            <Stat
              label="Score"
              value={anime.api_score?.toFixed(1) ?? "—"}
              accent
            />
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

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div>
      <div className="font-mono text-micro uppercase text-text-dim mb-0.5">
        {label}
      </div>
      <div
        className={
          accent
            ? "text-lg font-mono tnum text-amber-hi"
            : "text-lg font-mono tnum text-text"
        }
      >
        {value}
      </div>
    </div>
  );
}
