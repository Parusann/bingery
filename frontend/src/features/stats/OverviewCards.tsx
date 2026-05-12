import type { StatsOverview } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

const cards: Array<{
  key: keyof StatsOverview;
  label: string;
  format?: (v: unknown) => string;
}> = [
  { key: "total_rated", label: "Ratings" },
  { key: "total_watched", label: "Completed" },
  {
    key: "hours_watched",
    label: "Hours watched",
    format: (v) => Math.round(Number(v ?? 0)).toString(),
  },
  { key: "favorite_count", label: "Favorites" },
  {
    key: "avg_rating",
    label: "Avg rating",
    format: (v) => (v == null ? "—" : `${Number(v).toFixed(1)}/10`),
  },
  { key: "streak_days", label: "Streak (days)" },
];

export function OverviewCards({ overview }: { overview: StatsOverview }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => {
        const raw = overview[c.key];
        const formatted = c.format ? c.format(raw) : String(raw ?? "—");
        return (
          <GlassCard key={c.key} tone="warm" className="p-4">
            <div className="text-xs uppercase tracking-wider text-text-dim">
              {c.label}
            </div>
            <div className="font-display text-3xl text-amber mt-1 tabular-nums">
              {formatted}
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
}
