import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { GlassCard } from "@/design/GlassCard";
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
        <h1 className="font-display text-4xl mb-2">Sign in to see your picks</h1>
        <p className="text-text-muted">
          Rate a few anime and your personal recommendations appear here.
        </p>
      </div>
    );
  }

  const items = (recs.data?.recommendations ?? []).map((r) => r.anime);

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-6">For you</h1>
      <TasteProfile profile={recs.data?.taste_profile ?? null} />
      {recs.data?.recommendations?.length ? (
        <section>
          <h2 className="font-display text-2xl mb-4">Picks for tonight</h2>
          <AnimeGrid anime={items} loading={recs.isLoading} />
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            {(recs.data?.recommendations ?? []).slice(0, 6).map((r) => (
              <GlassCard key={r.anime.id} className="p-4">
                <div className="font-semibold mb-1">
                  {r.anime.title_english ?? r.anime.title}
                </div>
                <p className="text-sm text-text-muted">{r.reason}</p>
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
