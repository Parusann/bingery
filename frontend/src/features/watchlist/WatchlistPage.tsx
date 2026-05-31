import { useState } from "react";
import type { WatchStatus } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { StatusTabs } from "./StatusTabs";
import { WatchlistCard } from "./WatchlistCard";
import { useAuth } from "@/stores/auth";
import { useWatchlist, useWatchlistStats } from "@/hooks/useWatchlist";

export function WatchlistPage() {
  const user = useAuth((s) => s.user);
  const [status, setStatus] = useState<WatchStatus | null>(null);
  const wl = useWatchlist(status ?? undefined);
  const stats = useWatchlistStats();

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in to track</h1>
        <p className="text-text-muted">
          Your watching, completed, and plan-to-watch list lives here.
        </p>
      </div>
    );
  }

  const entries = wl.data?.entries ?? [];
  const gridCls =
    "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4";

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-5">Your watchlist</h1>
      <StatusTabs stats={stats.data?.stats} value={status} onChange={setStatus} />
      {wl.isLoading ? (
        <div className={gridCls}>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="aspect-[2/3]" rounded="lg" />
              <Skeleton className="h-3 mt-2 w-3/4" />
            </div>
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="py-24 text-center text-text-muted">
          Nothing here yet — add anime from the discover page.
        </div>
      ) : (
        <div className={gridCls}>
          {entries.map((e) => (
            <WatchlistCard key={e.id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}
