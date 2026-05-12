import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useCompare(a: string, b: string, enabled: boolean) {
  return useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => api.getCompare(a, b),
    enabled,
  });
}
