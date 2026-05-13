import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCollections() {
  return useQuery({
    queryKey: ["collections"],
    queryFn: () => api.getCollections(),
  });
}

export function useCollection(id: number | undefined) {
  return useQuery({
    queryKey: ["collection", id],
    queryFn: () => api.getCollection(id!),
    enabled: !!id,
  });
}

export function useSharedCollection(token: string | undefined) {
  return useQuery({
    queryKey: ["collection-share", token],
    queryFn: () => api.getSharedCollection(token!),
    enabled: !!token,
  });
}

export function useCreateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description?: string; is_public?: boolean }) =>
      api.createCollection(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });
}

export function useUpdateCollection(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title?: string; description?: string; is_public?: boolean }) =>
      api.updateCollection(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["collection", id] });
    },
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteCollection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });
}

export function useAddToCollection(collectionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { anime_id: number; note?: string }) =>
      api.addToCollection(collectionId, body),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["collection", collectionId] }),
  });
}

export function useRemoveFromCollection(collectionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) =>
      api.removeFromCollection(collectionId, animeId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["collection", collectionId] }),
  });
}
