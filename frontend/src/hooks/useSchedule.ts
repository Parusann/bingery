import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

export function useAnimeEpisodes(animeId: number, enabled = true) {
  const signedIn = useAuth((state) => !!state.user);
  return useQuery({
    queryKey: ["anime-episodes", animeId],
    queryFn: () => api.getAnimeEpisodes(animeId),
    enabled: signedIn && enabled,
  });
}
