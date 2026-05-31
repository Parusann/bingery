import { useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useScheduleWeek } from "@/hooks/useScheduleWeek";
import { ScheduleHeader } from "./ScheduleHeader";
import { DayStrip } from "./DayStrip";
import { DaySection } from "./DaySection";
import { getSundayOfWeek, shiftWeek, todayIsoDate } from "./utils";

type Lang = "sub" | "dub" | "both";

export function SchedulePage() {
  const user = useAuth((s) => s.user);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  const week = params.get("week");
  const lang = (params.get("lang") as Lang) || "both";
  const mine = params.get("mine") === "1";

  useEffect(() => {
    if (!week) {
      const sun = getSundayOfWeek(new Date());
      const p = new URLSearchParams(params);
      p.set("week", sun);
      navigate({ search: `?${p}` }, { replace: true });
    }
  }, [week, navigate, params]);

  const today = todayIsoDate();
  const q = useScheduleWeek(week ?? getSundayOfWeek(new Date()), lang, mine);

  const episodeCounts = useMemo(() => {
    const out: Record<string, number> = {};
    if (!q.data) return out;
    for (const d of q.data.days) out[d.date] = d.episodes.length;
    return out;
  }, [q.data]);

  // The schedule intentionally loads at the very top rather than auto-scrolling
  // to the current day — being jumped mid-page and then having to scroll all the
  // way back up was tedious. Jump to a specific day via the DayStrip chips; each
  // day also has a "back to top" control to return here.

  function setLang(next: Lang) {
    const p = new URLSearchParams(params);
    p.set("lang", next);
    setParams(p, { replace: true });
  }

  function toggleMine() {
    const p = new URLSearchParams(params);
    p.set("mine", mine ? "0" : "1");
    setParams(p, { replace: true });
  }

  function shift(weeks: number) {
    if (!week) return;
    const next = shiftWeek(week, weeks);
    const p = new URLSearchParams(params);
    p.set("week", next);
    setParams(p, { replace: true });
  }

  function scrollToDay(date: string) {
    const target = document.getElementById(`day-${date}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display italic text-4xl mb-2">Sign in to see the schedule</h1>
        <p className="text-text-muted">
          Track sub and dub episode releases for shows you're following.
        </p>
      </div>
    );
  }

  return (
    <div>
      <ScheduleHeader
        lang={lang}
        myShowsOnly={mine}
        onLangChange={setLang}
        onMineToggle={toggleMine}
      />
      <DayStrip
        weekStart={week ?? getSundayOfWeek(new Date())}
        todayIso={today}
        episodeCounts={episodeCounts}
        onChipClick={scrollToDay}
        onPrevWeek={() => shift(-1)}
        onNextWeek={() => shift(1)}
      />
      <div className="mt-10 space-y-14">
        {q.isLoading || !q.data
          ? Array.from({ length: 7 }).map((_, i) => (
              <div key={i} data-skeleton="true" className="space-y-3">
                <Skeleton className="h-[232px] rounded-[22px]" />
                <Skeleton className="h-24 rounded-lg" />
              </div>
            ))
          : q.data.days.map((d) => (
              <DaySection
                key={d.date}
                date={d.date}
                episodes={d.episodes}
                isToday={d.date === today}
                myShowsOnly={mine}
              />
            ))}
      </div>
    </div>
  );
}
