import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useAnimeDetail(id: number | undefined) {
  return useQuery({
    queryKey: ["anime-detail", id],
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
