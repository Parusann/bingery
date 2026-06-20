import type { StatsHeatmap } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

function intensity(count: number, max: number): string {
  if (count === 0) return "rgba(255,255,255,0.04)";
  const pct = Math.min(1, count / Math.max(1, max));
  const alpha = 0.18 + pct * 0.72;
  return `rgba(230,166,128,${alpha.toFixed(2)})`;
}

export function ActivityHeatmap({ data }: { data: StatsHeatmap }) {
  const byDate = new Map(data.cells.map((c) => [c.date, c.count]));
  const end = new Date();
  end.setHours(0, 0, 0, 0);
  const start = new Date(end);
  start.setDate(end.getDate() - 364);
  const startWeekday = start.getDay();
  start.setDate(start.getDate() - startWeekday);

  const cells: Array<{ date: string; count: number }> = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    const iso = cursor.toISOString().slice(0, 10);
    cells.push({ date: iso, count: byDate.get(iso) ?? 0 });
    cursor.setDate(cursor.getDate() + 1);
  }

  const weeks: Array<typeof cells> = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  return (
    <GlassCard className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl">Activity — last year</h2>
        <span className="text-xs text-text-dim">
          {data.cells.reduce((n, c) => n + c.count, 0)} events
        </span>
      </div>
      <div className="relative">
        <div className="flex gap-0.5 overflow-x-auto snap-x pb-1">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-0.5 snap-start">
              {week.map((cell) => (
                <div
                  key={cell.date}
                  className="w-2.5 h-2.5 rounded-[2px]"
                  style={{ background: intensity(cell.count, data.max) }}
                  title={`${cell.date} — ${cell.count}`}
                />
              ))}
            </div>
          ))}
        </div>
        <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-bg to-transparent sm:hidden" />
      </div>
    </GlassCard>
  );
}
