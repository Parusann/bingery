import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";

export function useCollections() {
  const userId = useAuth((s) => s.user?.id);
  return useQuery({
    queryKey: ["collections", userId],
    queryFn: () => api.getCollections(),
    enabled: !!userId,
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
    staleTime: 0,
  });
}

function refreshCollection(qc: QueryClient, id: number) {
  qc.invalidateQueries({ queryKey: ["collections"] });
  qc.invalidateQueries({ queryKey: ["collection", id] });
  qc.removeQueries({ queryKey: ["collection-share"] });
  qc.invalidateQueries({ queryKey: ["activity"] });
}

export function useCreateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string; is_public?: boolean }) => api.createCollection(body),
    onSuccess: ({ collection }) => refreshCollection(qc, collection.id),
  });
}

export function useUpdateCollection(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; is_public?: boolean }) => api.updateCollection(id, body),
    onSuccess: () => refreshCollection(qc, id),
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteCollection(id),
    onSuccess: (_response, id) => {
      qc.removeQueries({ queryKey: ["collection", id], type: "inactive" });
      refreshCollection(qc, id);
    },
  });
}

export function useAddToCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, animeId }: { id: number; animeId: number }) => api.addToCollection(id, { anime_id: animeId }),
    onSuccess: (_result, { id }) => refreshCollection(qc, id),
  });
}

export function useRemoveFromCollection(collectionId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.removeFromCollection(collectionId, animeId),
    onSuccess: () => refreshCollection(qc, collectionId),
  });
}
