import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSchedule(days = 7, kind: "sub" | "dub" | "both" = "sub") {
  return useQuery({
    queryKey: ["schedule", days, kind],
    queryFn: () => api.getSchedule(days, kind),
    staleTime: 60_000,
  });
}

export function useAnimeEpisodes(animeId: number, enabled = true) {
  return useQuery({
    queryKey: ["anime-episodes", animeId],
    queryFn: () => api.getAnimeEpisodes(animeId),
    enabled,
  });
}
