import { AnimeCard } from "@/features/discover/AnimeCard";
import type { SimilarAnime } from "@/types/api";

export function SimilarStrip({ similar }: { similar: SimilarAnime[] }) {
  if (!similar.length) return null;
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl mb-4">You might also like</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {similar.slice(0, 6).map((a, i) => (
          <div key={a.id}>
            <AnimeCard anime={a} index={i} />
            {a.shared_tags?.length ? (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {a.shared_tags.slice(0, 2).map((tag) => (
                  <span
                    key={tag}
                    className="px-1.5 py-0.5 rounded-md bg-white/[0.06] border border-border text-[10px] text-text-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
