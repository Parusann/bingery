import { useState } from "react";
import type { WatchStatus } from "@/types/models";
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { StatusTabs } from "./StatusTabs";
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

  const items = (wl.data?.entries ?? []).map((e) => e.anime);

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-5">Your watchlist</h1>
      <StatusTabs stats={stats.data?.stats} value={status} onChange={setStatus} />
      <AnimeGrid
        anime={items}
        loading={wl.isLoading}
        empty="Nothing here yet — add anime from the discover page."
      />
    </div>
  );
}
