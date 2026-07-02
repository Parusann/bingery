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
    // Skeleton mirrors the hero anatomy: poster + title + meta + description.
    return (
      <div className="space-y-6">
        <div className="rounded-xl border border-border bg-surface p-4 sm:p-6 md:p-10">
          <div className="flex flex-col md:flex-row gap-6 md:gap-8">
            <Skeleton className="w-40 md:w-56 aspect-[2/3] shrink-0" rounded="lg" />
            <div className="flex-1 space-y-3 min-w-0">
              <Skeleton className="h-10 w-2/3" />
              <Skeleton className="h-4 w-1/3" />
              <div className="flex gap-1.5 pt-1">
                <Skeleton className="h-6 w-16" rounded="full" />
                <Skeleton className="h-6 w-20" rounded="full" />
                <Skeleton className="h-6 w-14" rounded="full" />
              </div>
              <Skeleton className="h-24 w-full max-w-3xl" />
            </div>
          </div>
        </div>
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
      <div className="grid md:grid-cols-[1fr_420px] gap-8 mt-8">
        <section>
          <h2 className="font-display text-title mb-4">Community fan genres</h2>
          <GlassCard className="p-4 sm:p-6">
            {anime.fan_genres && anime.fan_genres.length ? (
              <FanGenreBars fanGenres={anime.fan_genres} />
            ) : (
              <p className="font-display italic text-text-muted">
                No fan-genre votes yet. Be the first.
              </p>
            )}
          </GlassCard>
          <RelatedStrip related={related.data?.related ?? []} />
        </section>
        <aside>
          <h2 className="font-display text-title mb-4">Your rating</h2>
          <GlassCard tone="warm" className="p-4 sm:p-6">
            <RatingPanel anime={anime} />
          </GlassCard>
        </aside>
      </div>
      <SimilarStrip similar={similar.data?.similar ?? []} />
    </article>
  );
}
