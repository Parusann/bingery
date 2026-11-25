import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

export function useScheduleWeek(
  week: string,
  lang: "sub" | "dub" | "both" = "both",
  mine = false,
) {
  const signedIn = useAuth((state) => !!state.user);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return useQuery({
    queryKey: ["schedule-week", week, lang, mine, tz],
    queryFn: () => api.getScheduleWeek(week, lang, mine, tz),
    staleTime: 60_000,
    enabled: signedIn && Boolean(week),
  });
}
