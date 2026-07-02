import { AnimeCard } from "@/features/discover/AnimeCard";
import type { SimilarAnime } from "@/types/api";
import type { AnimeSummary } from "@/types/models";

export function BecauseYouLovedRow({
  data,
}: {
  data?: { seed: AnimeSummary; items: SimilarAnime[] };
}) {
  if (!data || !data.items.length) return null;
  const seedTitle = data.seed.title_english ?? data.seed.title;
  return (
    <section className="mt-12">
      <h2 className="font-display text-title mb-4">
        Because you loved{" "}
        <span className="italic text-amber-hi">{seedTitle}</span>
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-x-4 gap-y-6">
        {data.items.slice(0, 6).map((a, i) => (
          <AnimeCard key={a.id} anime={a} index={i} />
        ))}
      </div>
    </section>
  );
}
