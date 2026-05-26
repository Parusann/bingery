import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useScheduleWeek(
  week: string,
  lang: "sub" | "dub" | "both" = "both",
  mine = false,
) {
  return useQuery({
    queryKey: ["schedule-week", week, lang, mine],
    queryFn: () => api.getScheduleWeek(week, lang, mine),
    staleTime: 60_000,
    enabled: Boolean(week),
  });
}
