import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useStatsOverview(enabled = true) {
  return useQuery({
    queryKey: ["stats-overview"],
    queryFn: () => api.getStatsOverview(),
    enabled,
    staleTime: 60_000,
  });
}

export function useStatsHeatmap(enabled = true) {
  return useQuery({
    queryKey: ["stats-heatmap"],
    queryFn: () => api.getStatsHeatmap(),
    enabled,
    staleTime: 60_000,
  });
}
