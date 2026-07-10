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

// Stat tiles: mono micro labels, big ink serif numerals. Amber stays
// reserved for interaction — a wall of six amber numbers read as noise.
export function OverviewCards({ overview }: { overview: StatsOverview }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((c) => {
        const raw = overview[c.key];
        const formatted = c.format ? c.format(raw) : String(raw ?? "—");
        return (
          <GlassCard key={c.key} tone="warm" className="p-4">
            <div className="font-mono text-micro uppercase text-text-dim">
              {c.label}
            </div>
            <div className="font-display text-3xl text-text mt-1.5 tnum">
              {formatted}
            </div>
          </GlassCard>
        );
      })}
    </div>
  );
}
