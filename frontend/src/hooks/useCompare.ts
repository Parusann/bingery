import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// Anime-vs-anime comparison. Pass two anime IDs; the query is disabled
// until BOTH are present so the UI can stage one pick at a time.
export function useCompare(aId: number | null, bId: number | null) {
  return useQuery({
    queryKey: ["compare", aId, bId],
    queryFn: () => api.compareAnime(aId as number, bId as number),
    enabled: aId != null && bId != null,
    staleTime: 60_000,
  });
}
