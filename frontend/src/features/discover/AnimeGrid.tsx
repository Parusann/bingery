import type { AnimeSummary } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { ScrollReveal } from "@/design/ScrollReveal";
import { AnimeCard } from "./AnimeCard";

interface Props {
  anime: AnimeSummary[];
  loading?: boolean;
  empty?: React.ReactNode;
}

export function AnimeGrid({ anime, loading, empty }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="aspect-[2/3]" rounded="lg" />
            <Skeleton className="h-3 mt-2 w-3/4" />
          </div>
        ))}
      </div>
    );
  }
  if (!anime.length) {
    return (
      <div className="py-24 text-center text-text-muted">
        {empty ?? "No anime found."}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
      {anime.map((a, i) => (
        <ScrollReveal key={a.id} delay={Math.min(i, 14) * 0.03}>
          <AnimeCard anime={a} index={0} />
        </ScrollReveal>
      ))}
    </div>
  );
}
