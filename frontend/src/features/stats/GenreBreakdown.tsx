import type { StatsGenreSlice } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { genreColor } from "@/lib/genres";

export function GenreBreakdown({ slices }: { slices: StatsGenreSlice[] }) {
  const total = slices.reduce((n, s) => n + s.count, 0);
  return (
    <GlassCard tone="cool" className="p-6">
      <h2 className="font-display text-xl mb-4">Top genres</h2>
      <div className="space-y-2">
        {slices.slice(0, 8).map((s) => {
          const pct = total > 0 ? (s.count / total) * 100 : 0;
          return (
            <div key={s.genre} className="flex items-center gap-3 text-sm">
              <div className="w-32 shrink-0 text-text-muted">{s.genre}</div>
              <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full"
                  style={{ width: `${pct}%`, background: genreColor(s.genre) }}
                />
              </div>
              <div className="w-10 text-right font-mono text-text-muted tabular-nums">
                {s.count}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
