import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSubmitReview(animeId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { score: number; review?: string; genres?: string[] }) =>
      api.submitReview(animeId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["anime-detail", animeId] });
    },
  });
}
