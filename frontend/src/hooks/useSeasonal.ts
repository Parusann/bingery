import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Season } from "@/types/models";

export function useSeasonal(year?: number, season?: Season) {
  return useQuery({
    queryKey: ["seasonal", year ?? "current", season ?? "current"],
    queryFn: () => api.getSeasonal(year, season),
  });
}

export function currentSeason(now = new Date()): { year: number; season: Season } {
  const m = now.getMonth();
  const season: Season =
    m < 3 ? "winter" : m < 6 ? "spring" : m < 9 ? "summer" : "fall";
  return { year: now.getFullYear(), season };
}
