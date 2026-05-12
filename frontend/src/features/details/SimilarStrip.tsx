import type { AnimeSummary } from "@/types/models";
import { AnimeCard } from "@/features/discover/AnimeCard";

export function SimilarStrip({ similar }: { similar: AnimeSummary[] }) {
  if (!similar.length) return null;
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl mb-4">You might also like</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {similar.slice(0, 6).map((a, i) => (
          <AnimeCard key={a.id} anime={a} index={i} />
        ))}
      </div>
    </section>
  );
}
