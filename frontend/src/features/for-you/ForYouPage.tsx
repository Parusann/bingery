import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useRecommendations } from "@/hooks/useRecommendations";
import { BecauseYouLovedRow } from "./BecauseYouLovedRow";
import { TasteProfile } from "./TasteProfile";

export function ForYouPage() {
  const user = useAuth((s) => s.user);
  const recs = useRecommendations(!!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <div className="font-mono text-micro uppercase text-amber mb-3">
          For you
        </div>
        <h1 className="font-display text-display mb-2">
          Sign in to see your picks
        </h1>
        <p className="text-text-muted">
          Rate a few anime and your personal recommendations appear here.
        </p>
      </div>
    );
  }

  const items = (recs.data?.recommendations ?? []).map((r) => r.anime);

  return (
    <div>
      <div className="mb-6">
        <div className="font-mono text-micro uppercase text-amber mb-2">
          Personalized
        </div>
        <h1 className="font-display text-display">For you</h1>
      </div>
      {recs.isLoading ? (
        // Mirrors the TasteProfile card: heading row + genre bars.
        <GlassCard tone="warm" className="p-6 mb-8">
          <div className="flex items-baseline justify-between mb-4">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-40" />
          </div>
          <div className="space-y-2.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        </GlassCard>
      ) : (
        <TasteProfile profile={recs.data?.taste_profile ?? null} />
      )}
      {recs.data?.recommendations?.length ? (
        <section>
          <h2 className="font-display text-title mb-4">Picks for tonight</h2>
          <AnimeGrid anime={items} loading={recs.isLoading} />
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            {(recs.data?.recommendations ?? []).slice(0, 6).map((r) => (
              <GlassCard key={r.anime.id} className="relative p-4 pl-5 overflow-hidden">
                <span
                  aria-hidden
                  className="absolute left-0 top-3 bottom-3 w-[3px] rounded-r-sm bg-gradient-to-b from-amber to-amber/30"
                />
                <div className="font-medium mb-1">
                  {r.anime.title_english ?? r.anime.title}
                </div>
                <p className="font-display italic text-sm text-text-muted">
                  {r.reason}
                </p>
              </GlassCard>
            ))}
          </div>
        </section>
      ) : (
        <AnimeGrid
          anime={[]}
          loading={recs.isLoading}
          empty="Rate a few anime to get personalized picks."
        />
      )}
      <BecauseYouLovedRow data={recs.data?.because_you_loved} />
    </div>
  );
}
