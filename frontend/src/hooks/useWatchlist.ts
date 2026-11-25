import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import type { WatchStatus } from "@/types/models";
import type { AnimeDetailResponse } from "@/types/api";

export function useWatchlist() {
  const user = useAuth((s) => s.user);
  return useQuery({
    queryKey: ["watchlist", "all"],
    // Load the entire list once; all filtering/sorting happens client-side.
    queryFn: () => api.getWatchlist("?all=1"),
    // Signed-out visitors have no watchlist — don't fire guaranteed 401s.
    enabled: !!user,
  });
}

export function useWatchlistStats() {
  const user = useAuth((s) => s.user);
  return useQuery({
    queryKey: ["watchlist-stats"],
    queryFn: () => api.getWatchlistStats(),
    enabled: !!user,
  });
}

// Invalidate the lists/stats AND the per-anime detail query — the detail page's
// status pills + favorite read from ["anime-detail", id], so without this they
// never reflected a saved change (the bug behind "no visual cue").
function invalidateFor(
  qc: ReturnType<typeof useQueryClient>,
  animeId: number
) {
  qc.invalidateQueries({ queryKey: ["watchlist"] });
  qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
  qc.invalidateQueries({ queryKey: ["schedule-week"] });
  qc.invalidateQueries({ queryKey: ["activity"] });
  qc.invalidateQueries({ queryKey: ["stats-overview"] });
  qc.invalidateQueries({ queryKey: ["stats-heatmap"] });
  qc.invalidateQueries({ queryKey: ["recommendations"] });
  return qc.invalidateQueries({ queryKey: ["anime-detail", animeId] });
}

export function useSetWatchStatus() {
  const qc = useQueryClient();
  const userId = useAuth((s) => s.user?.id);
  return useMutation({
    mutationFn: ({
      animeId,
      status,
      episodesWatched,
    }: {
      animeId: number;
      status: WatchStatus;
      episodesWatched?: number;
    }) => api.setWatchStatus(animeId, { status, episodes_watched: episodesWatched }),
    onSuccess: ({ entry }, { animeId }) => {
      qc.setQueryData<AnimeDetailResponse>(["anime-detail", animeId, userId], (detail) =>
        detail && { ...detail, anime: { ...detail.anime, user_watch_status: entry } }
      );
      return invalidateFor(qc, animeId);
    },
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.toggleFavorite(animeId),
    onSuccess: (_data, animeId) => invalidateFor(qc, animeId),
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.removeFromWatchlist(animeId),
    onSuccess: (_data, animeId) => invalidateFor(qc, animeId),
  });
}
