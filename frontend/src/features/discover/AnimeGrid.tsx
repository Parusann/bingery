import type { AnimeSummary } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { AnimeCard } from "./AnimeCard";

interface Props {
  anime: AnimeSummary[];
  loading?: boolean;
  empty?: React.ReactNode;
  featureFirst?: boolean;
  scoreSource?: "api_score" | "community_score";
}

export function AnimeGrid({ anime, loading, empty, featureFirst, scoreSource }: Props) {
  if (loading) {
    return (
      <div className="catalog-grid" aria-busy="true" aria-label="Loading titles">
        {Array.from({ length: 12 }, (_, index) => (
          <div key={index} className={featureFirst && index === 0 ? "catalog-grid__lead" : undefined}>
            <Skeleton className={featureFirst && index === 0 ? "aspect-[1.5] h-full" : "aspect-[2/3]"} rounded="lg" />
            {!(featureFirst && index === 0) && (
              <div className="pt-2.5 space-y-2">
                <Skeleton className="h-3 w-3/5" /><Skeleton className="h-4 w-11/12" />
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }
  if (!anime.length) {
    return <div className="catalog-empty">{empty ?? "No anime found."}</div>;
  }
  return (
    <div className="catalog-grid">
      {anime.map((item, index) => (
        <AnimeCard key={item.id} anime={item} featured={featureFirst && index === 0} scoreSource={scoreSource} />
      ))}
    </div>
  );
}
