import type { StatsGenreSlice } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { genreColor } from "@/lib/genres";

export function GenreBreakdown({ slices }: { slices: StatsGenreSlice[] }) {
  const total = slices.reduce((n, s) => n + s.count, 0);
  return (
    <GlassCard tone="cool" className="p-6">
      <h2 className="font-display text-heading mb-4">Top genres</h2>
      <div className="space-y-2.5">
        {slices.slice(0, 8).map((s) => {
          const pct = total > 0 ? (s.count / total) * 100 : 0;
          const c = genreColor(s.genre);
          return (
            <div key={s.genre} className="flex items-center gap-3 text-sm">
              <div className="w-32 shrink-0 text-caption text-text-muted truncate">
                {s.genre}
              </div>
              <div className="flex-1 h-2 rounded-pill bg-surface overflow-hidden">
                <div
                  className="h-full rounded-pill"
                  style={{
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, ${c}99, ${c})`,
                  }}
                />
              </div>
              <div className="w-10 text-right font-mono text-caption tnum text-text-dim">
                {s.count}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
