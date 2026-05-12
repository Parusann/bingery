import type { AnimeSummary } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
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
        <AnimeCard key={a.id} anime={a} index={i} />
      ))}
    </div>
  );
}
