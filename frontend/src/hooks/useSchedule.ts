import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useAnimeEpisodes(animeId: number, enabled = true) {
  return useQuery({
    queryKey: ["anime-episodes", animeId],
    queryFn: () => api.getAnimeEpisodes(animeId),
    enabled,
  });
}
