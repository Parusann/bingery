import type { StatsHeatmap } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { cn } from "@/lib/cn";

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// "Your rhythm" — replaces the borrowed GitHub-style heatmap with insights
// the data can actually support: WHEN you watch. Everything below is derived
// from the same StatsHeatmap cells ({date, count}); the hook and props are
// untouched, only the presentation changed.
export function ActivityHeatmap({ data }: { data: StatsHeatmap }) {
  const byDate = new Map(data.cells.map((c) => [c.date, c.count]));
  const end = new Date();
  end.setHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setDate(end.getDate() - 364);

  // Zero-filled day series (needed for streaks + weekday shares).
  const days: Array<{ date: string; weekday: number; count: number }> = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    const iso = cursor.toISOString().slice(0, 10);
    days.push({ date: iso, weekday: cursor.getDay(), count: byDate.get(iso) ?? 0 });
    cursor.setDate(cursor.getDate() + 1);
  }

  const totalEvents = days.reduce((n, d) => n + d.count, 0);

  // Weekday rhythm
  const byWeekday = Array.from({ length: 7 }, () => 0);
  for (const d of days) byWeekday[d.weekday] += d.count;
  const maxWeekday = Math.max(1, ...byWeekday);
  const peakWeekday = byWeekday.indexOf(Math.max(...byWeekday));
  const peakShare = totalEvents > 0 ? Math.round((byWeekday[peakWeekday] / totalEvents) * 100) : 0;

  // Monthly film strip (oldest → newest)
  const monthMap = new Map<string, { label: string; count: number }>();
  for (const d of days) {
    const key = d.date.slice(0, 7);
    if (!monthMap.has(key)) {
      monthMap.set(key, {
        label: new Date(`${d.date}T00:00:00`).toLocaleDateString(undefined, { month: "short" }),
        count: 0,
      });
    }
    monthMap.get(key)!.count += d.count;
  }
  const months = [...monthMap.entries()].map(([key, v]) => ({ key, ...v }));
  const maxMonth = Math.max(1, ...months.map((m) => m.count));
  const busiest = months.reduce((a, b) => (b.count > a.count ? b : a), months[0]);

  // Earned facts
  let biggest = { date: "", count: 0 };
  for (const d of days) if (d.count > biggest.count) biggest = d;
  let streak = 0;
  let run = 0;
  for (const d of days) {
    run = d.count > 0 ? run + 1 : 0;
    if (run > streak) streak = run;
  }
  const fmtDay = (iso: string) =>
    iso
      ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })
      : "—";

  return (
    <GlassCard className="p-6">
      <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
        <h2 className="font-display text-heading">Your rhythm</h2>
        <span className="font-mono text-caption tnum text-text-dim">
          {totalEvents} events · last year
        </span>
      </div>

      {totalEvents === 0 ? (
        <p className="font-display italic text-text-muted py-8 text-center">
          No activity yet — episodes you log will shape your rhythm.
        </p>
      ) : (
        <>
          <p className="font-display italic text-title text-text-muted mb-6 max-w-2xl">
            Most of your watching lands on{" "}
            <span className="text-amber-hi not-italic font-semibold">
              {WEEKDAYS[peakWeekday]}s
            </span>{" "}
            — {peakShare}% of the year.
          </p>

          {/* Twelve months, one strip of film */}
          <div className="mb-6">
            <div className="font-mono text-micro uppercase text-text-dim mb-2.5">
              Twelve months, one strip of film
            </div>
            <div
              className="flex gap-1"
              role="img"
              aria-label={`Monthly activity: busiest month ${busiest?.label ?? "—"} with ${busiest?.count ?? 0} events`}
            >
              {months.map((m) => {
                const ratio = m.count / maxMonth;
                const isPeak = m.key === busiest?.key;
                return (
                  <div key={m.key} className="flex-1 min-w-0">
                    <div
                      className={cn(
                        "relative h-14 rounded-sm border overflow-hidden",
                        isPeak ? "border-amber/60" : "border-border"
                      )}
                      style={{ background: `rgba(239,171,129,${(0.05 + ratio * 0.65).toFixed(2)})` }}
                      title={`${m.label} — ${m.count} events`}
                    >
                      {/* sprocket holes */}
                      <div aria-hidden className="absolute top-1 inset-x-1.5 flex justify-between">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="w-1 h-1 rounded-[1px] bg-bg/80" />
                        ))}
                      </div>
                      <div aria-hidden className="absolute bottom-1 inset-x-1.5 flex justify-between">
                        {[0, 1, 2].map((i) => (
                          <span key={i} className="w-1 h-1 rounded-[1px] bg-bg/80" />
                        ))}
                      </div>
                    </div>
                    <div className="mt-1 text-center font-mono text-[9px] uppercase text-text-dim">
                      {m.label}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="grid md:grid-cols-[1fr_auto] gap-6 items-end">
            {/* Weekday rhythm */}
            <div>
              <div className="font-mono text-micro uppercase text-text-dim mb-2.5">
                Weekday rhythm
              </div>
              <div
                className="grid grid-cols-7 gap-2 items-end h-32"
                role="img"
                aria-label={`Weekday rhythm: peak on ${WEEKDAYS[peakWeekday]} with ${byWeekday[peakWeekday]} events`}
              >
                {byWeekday.map((v, i) => {
                  const h = (v / maxWeekday) * 100;
                  const peak = i === peakWeekday && v > 0;
                  return (
                    <div key={i} className="flex h-full flex-col items-center justify-end gap-1.5">
                      <div
                        title={`${WEEKDAYS[i]} — ${v} events`}
                        className={cn(
                          "w-full rounded-md",
                          peak
                            ? "bg-gradient-to-t from-amber-deep to-amber-hi"
                            : "bg-gradient-to-t from-amber/20 to-amber/50"
                        )}
                        style={{ height: `${Math.max(4, h)}%` }}
                      />
                      <span
                        className={cn(
                          "font-mono text-[9px] uppercase",
                          peak ? "text-amber-hi" : "text-text-dim"
                        )}
                      >
                        {WEEKDAYS[i].slice(0, 3)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Earned facts */}
            <div className="flex md:flex-col flex-wrap gap-2">
              <Fact label="Biggest day" value={`${fmtDay(biggest.date)} · ${biggest.count}`} />
              <Fact label="Longest streak" value={`${streak} days`} />
              <Fact label="Busiest month" value={busiest?.label ?? "—"} />
            </div>
          </div>
        </>
      )}
    </GlassCard>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3.5 py-2.5 min-w-[140px]">
      <div className="font-mono text-micro uppercase text-text-dim">{label}</div>
      <div className="mt-0.5 text-sm font-medium tnum">{value}</div>
    </div>
  );
}
