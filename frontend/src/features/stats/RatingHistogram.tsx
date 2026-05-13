import type { StatsRatingBucket } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

export function RatingHistogram({ buckets }: { buckets: StatsRatingBucket[] }) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <GlassCard className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl">Rating distribution</h2>
        <span className="text-xs text-text-dim uppercase tracking-wider">
          1 — 10
        </span>
      </div>
      <div className="grid grid-cols-10 gap-2 items-end h-40">
        {Array.from({ length: 10 }).map((_, i) => {
          const score = i + 1;
          const bucket = buckets.find((b) => b.score === score);
          const count = bucket?.count ?? 0;
          const h = (count / max) * 100;
          return (
            <div key={score} className="flex flex-col items-center gap-1">
              <div
                className="w-full rounded-t-sm bg-gradient-to-t from-amber to-amber-soft"
                style={{ height: `${Math.max(2, h)}%` }}
                title={`${count} at ${score}/10`}
              />
              <div className="text-xs text-text-muted tabular-nums">{score}</div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
