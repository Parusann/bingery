import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

export function useAnimeDetail(id: number | undefined) {
  const userId = useAuth((s) => s.user?.id);
  return useQuery({
    queryKey: ["anime-detail", id, userId],
    queryFn: () => api.getAnimeDetail(id!),
    enabled: !!id,
  });
}

export function useSimilar(id: number | undefined) {
  return useQuery({
    queryKey: ["anime-similar", id],
    queryFn: () => api.getSimilar(id!),
    enabled: !!id,
  });
}

export function useRelated(id: number | undefined) {
  return useQuery({
    queryKey: ["anime-related", id],
    queryFn: () => api.getRelated(id!),
    enabled: !!id,
  });
}
