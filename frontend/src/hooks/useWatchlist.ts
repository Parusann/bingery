import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { WatchStatus } from "@/types/models";

export function useWatchlist(status?: WatchStatus) {
  return useQuery({
    queryKey: ["watchlist", status ?? "all"],
    queryFn: () => api.getWatchlist(status ? `?status=${status}` : ""),
  });
}

export function useWatchlistStats() {
  return useQuery({
    queryKey: ["watchlist-stats"],
    queryFn: () => api.getWatchlistStats(),
  });
}

export function useSetWatchStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      animeId,
      status,
    }: {
      animeId: number;
      status: WatchStatus;
    }) => api.setWatchStatus(animeId, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
    },
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.toggleFavorite(animeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
    },
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.removeFromWatchlist(animeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
    },
  });
}
