import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useStatsHeatmap, useStatsOverview } from "@/hooks/useStats";
import { OverviewCards } from "./OverviewCards";
import { RatingHistogram } from "./RatingHistogram";
import { GenreBreakdown } from "./GenreBreakdown";
import { ActivityHeatmap } from "./ActivityHeatmap";

export function StatsPage() {
  const user = useAuth((s) => s.user);
  const overview = useStatsOverview(!!user);
  const heatmap = useStatsHeatmap(!!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <div className="font-mono text-micro uppercase text-amber mb-3">
          Stats
        </div>
        <h1 className="font-display text-display mb-2">
          Sign in for your stats
        </h1>
        <p className="text-text-muted">
          See your rating distribution, heatmap, and top genres.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <div className="font-mono text-micro uppercase text-amber mb-2">
          Your year in anime
        </div>
        <h1 className="font-display text-display">Your stats</h1>
      </div>
      {overview.isLoading || !overview.data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px]" rounded="lg" />
          ))}
        </div>
      ) : (
        <OverviewCards overview={overview.data.overview} />
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {overview.data ? (
          <>
            <RatingHistogram buckets={overview.data.rating_distribution} />
            <GenreBreakdown slices={overview.data.top_genres} />
          </>
        ) : (
          <>
            <Skeleton className="h-64" rounded="lg" />
            <Skeleton className="h-64" rounded="lg" />
          </>
        )}
      </div>
      {heatmap.data ? (
        <ActivityHeatmap data={heatmap.data.heatmap} />
      ) : (
        <Skeleton className="h-48" rounded="lg" />
      )}
    </div>
  );
}
