import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useStatsOverview } from "@/hooks/useStats";
import { OverviewCards } from "./OverviewCards";

export function StatsPage() {
  const user = useAuth((s) => s.user);
  const overview = useStatsOverview(!!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in for your stats</h1>
        <p className="text-text-muted">
          See your rating distribution, heatmap, and top genres.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <h1 className="font-display text-4xl text-amber">Your stats</h1>
      {overview.isLoading || !overview.data ? (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20" rounded="lg" />
          ))}
        </div>
      ) : (
        <OverviewCards overview={overview.data.overview} />
      )}
    </div>
  );
}
