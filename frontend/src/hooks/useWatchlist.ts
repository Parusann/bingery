import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import type { WatchStatus } from "@/types/models";

export function useWatchlist(status?: WatchStatus) {
  const user = useAuth((s) => s.user);
  return useQuery({
    queryKey: ["watchlist", status ?? "all"],
    queryFn: () => api.getWatchlist(status ? `?status=${status}` : ""),
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
  qc.invalidateQueries({ queryKey: ["anime-detail", animeId] });
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
    onSuccess: (_data, { animeId }) => invalidateFor(qc, animeId),
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
