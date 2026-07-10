import type { AnimeSummary } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { ScrollReveal } from "@/design/ScrollReveal";
import { AnimeCard } from "./AnimeCard";

interface Props {
  anime: AnimeSummary[];
  loading?: boolean;
  empty?: React.ReactNode;
}

const GRID = "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-x-4 gap-y-6";

export function AnimeGrid({ anime, loading, empty }: Props) {
  if (loading) {
    // Skeletons mirror the final card anatomy: poster, two title lines.
    return (
      <div className={GRID}>
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="aspect-[2/3]" rounded="lg" />
            <div className="px-0.5 pt-2.5 space-y-1.5">
              <Skeleton className="h-3.5 w-11/12" />
              <Skeleton className="h-3 w-3/5" />
            </div>
          </div>
        ))}
      </div>
    );
  }
  if (!anime.length) {
    return (
      <div className="py-24 text-center">
        <div className="font-mono text-micro uppercase text-text-dim mb-3">
          No results
        </div>
        <p className="font-display italic text-title text-text-muted max-w-md mx-auto">
          {empty ?? "No anime found."}
        </p>
      </div>
    );
  }
  return (
    <div className={GRID}>
      {anime.map((a, i) => (
        <ScrollReveal key={a.id} delay={Math.min(i, 14) * 0.03}>
          <AnimeCard anime={a} />
        </ScrollReveal>
      ))}
    </div>
  );
}
