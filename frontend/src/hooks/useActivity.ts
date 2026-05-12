import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useActivity(page: number, enabled = true) {
  return useQuery({
    queryKey: ["activity", page],
    queryFn: () => api.getActivity(page),
    enabled,
  });
}
