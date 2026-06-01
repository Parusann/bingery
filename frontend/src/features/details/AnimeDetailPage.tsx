import { useParams } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { useAnimeDetail, useSimilar, useRelated } from "@/hooks/useAnimeDetail";
import { WatchStatusSelector } from "@/features/watchlist/WatchStatusSelector";
import { AddToCollection } from "@/features/collections/AddToCollection";
import { useAuth } from "@/stores/auth";
import { DetailHero } from "./DetailHero";
import { DubReportButton } from "./DubReportButton";
import { FanGenreBars } from "./FanGenreBars";
import { NextEpisodeWidget } from "./NextEpisodeWidget";
import { RatingPanel } from "./RatingPanel";
import { SimilarStrip } from "./SimilarStrip";
import { RelatedStrip } from "./RelatedStrip";

export function AnimeDetailPage() {
  const { id } = useParams();
  const numericId = id ? Number(id) : undefined;
  const user = useAuth((s) => s.user);
  const detail = useAnimeDetail(numericId);
  const similar = useSimilar(numericId);
  const related = useRelated(numericId);

  if (detail.isLoading || !detail.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-72" rounded="lg" />
        <Skeleton className="h-48" rounded="lg" />
      </div>
    );
  }
  const anime = detail.data.anime;
  const actions = user ? (
    <>
      <WatchStatusSelector
        animeId={anime.id}
        current={anime.user_watch_status?.status ?? null}
        isFavorite={anime.user_watch_status?.is_favorite ?? false}
      />
      <AddToCollection animeId={anime.id} />
    </>
  ) : null;

  return (
    <article>
      <DetailHero anime={anime} actions={actions} />
      <NextEpisodeWidget animeId={anime.id} />
      {user ? (
        <div className="mt-3">
          <DubReportButton animeId={anime.id} />
        </div>
      ) : null}
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
          <RelatedStrip related={related.data?.related ?? []} />
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
