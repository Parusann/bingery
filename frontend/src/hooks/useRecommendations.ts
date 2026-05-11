import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRecommendations(enabled: boolean) {
  return useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api.getRecs(),
    enabled,
    staleTime: 5 * 60_000,
  });
}
