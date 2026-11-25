import { SignInPanel, LoadError } from "@/design/PageState";
import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useScheduleWeek } from "@/hooks/useScheduleWeek";
import { ScheduleHeader } from "./ScheduleHeader";
import { DayStrip } from "./DayStrip";
import { DaySection } from "./DaySection";
import { getSundayOfWeek, shiftWeek, todayIsoDate, toLocalIsoDate } from "./utils";

type Lang = "sub" | "dub" | "both";

export function SchedulePage() {
  const user = useAuth((s) => s.user);
  const [params, setParams] = useSearchParams();
  const rawWeek = params.get("week");
  const parsed = rawWeek && /^\d{4}-\d{2}-\d{2}$/.test(rawWeek)
    ? new Date(rawWeek + "T12:00:00") : null;
  const week = parsed && !Number.isNaN(parsed.getTime()) && toLocalIsoDate(parsed) === rawWeek &&
    parsed.getFullYear() >= 1000 && parsed.getFullYear() <= 9998
    ? getSundayOfWeek(parsed) : getSundayOfWeek(new Date());
  const rawLang = params.get("lang");
  const lang: Lang = rawLang === "sub" || rawLang === "dub" ? rawLang : "both";
  const mine = params.get("mine") === "1";

  useEffect(() => {
    if (rawWeek === week && (!rawLang || rawLang === lang)) return;
    const next = new URLSearchParams(params);
    next.set("week", week);
    if (rawLang) next.set("lang", lang);
    setParams(next, { replace: true, preventScrollReset: true });
  }, [rawWeek, week, rawLang, lang, params, setParams]);

  const today = todayIsoDate();
  const q = useScheduleWeek(week, lang, mine);

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
    setParams(p, { replace: true, preventScrollReset: true });
  }

  function toggleMine() {
    const p = new URLSearchParams(params);
    p.set("mine", mine ? "0" : "1");
    setParams(p, { replace: true, preventScrollReset: true });
  }

  function shift(weeks: number) {
    const next = shiftWeek(week, weeks);
    const p = new URLSearchParams(params);
    p.set("week", next);
    setParams(p, { replace: true, preventScrollReset: true });
  }

  function scrollToDay(date: string) {
    const target = document.getElementById(`day-${date}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (!user) {
    return <SignInPanel section="Schedule" title="Sign in to see the schedule"
      description="Follow weekly sub and dub releases and see when your shows air." />;
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
        weekStart={week}
        todayIso={today}
        episodeCounts={episodeCounts}
        onChipClick={scrollToDay}
        onPrevWeek={() => shift(-1)}
        onNextWeek={() => shift(1)}
      />
      <div className="mt-10 space-y-14">
        {q.isError && !q.data ? <LoadError title="This week’s schedule couldn’t load." retry={() => q.refetch()} />
          : q.isLoading || !q.data
          ? Array.from({ length: 7 }).map((_, i) => (
              // Mirrors the real day anatomy: banner (232px, xl radius) +
              // two episode rows.
              <div key={i} data-skeleton="true" className="space-y-3">
                <Skeleton className="h-[232px] rounded-[22px]" />
                <Skeleton className="h-[92px] rounded-lg" />
                <Skeleton className="h-[92px] rounded-lg" />
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
