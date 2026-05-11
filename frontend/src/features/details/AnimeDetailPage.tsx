import { useParams } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { useAnimeDetail, useSimilar } from "@/hooks/useAnimeDetail";
import { DetailHero } from "./DetailHero";
import { FanGenreBars } from "./FanGenreBars";
import { RatingPanel } from "./RatingPanel";
import { SimilarStrip } from "./SimilarStrip";

export function AnimeDetailPage() {
  const { id } = useParams();
  const numericId = id ? Number(id) : undefined;
  const detail = useAnimeDetail(numericId);
  const similar = useSimilar(numericId);

  if (detail.isLoading || !detail.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-72" rounded="lg" />
        <Skeleton className="h-48" rounded="lg" />
      </div>
    );
  }
  const anime = detail.data.anime;
  return (
    <article>
      <DetailHero anime={anime} />
      <div className="grid md:grid-cols-[1fr_420px] gap-8">
        <section>
          <h2 className="font-display text-2xl mb-4">Community fan genres</h2>
          <GlassCard className="p-6">
            {anime.fan_genres && anime.fan_genres.length ? (
              <FanGenreBars fanGenres={anime.fan_genres} />
            ) : (
              <p className="text-text-muted text-sm">
                No fan-genre votes yet. Be the first.
              </p>
            )}
          </GlassCard>
        </section>
        <aside>
          <h2 className="font-display text-2xl mb-4">Your rating</h2>
          <GlassCard tone="warm" className="p-6">
            <RatingPanel anime={anime} />
          </GlassCard>
        </aside>
      </div>
      <SimilarStrip similar={similar.data?.similar ?? []} />
    </article>
  );
}
