import type { StatsRatingBucket } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";

export function RatingHistogram({ buckets }: { buckets: StatsRatingBucket[] }) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <GlassCard className="p-6">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-heading">Rating distribution</h2>
        <span className="font-mono text-micro uppercase text-text-dim">
          1 — 10
        </span>
      </div>
      <div className="grid grid-cols-10 gap-1.5 items-end h-40 border-b border-border pb-px">
        {Array.from({ length: 10 }).map((_, i) => {
          const score = i + 1;
          const bucket = buckets.find((b) => b.score === score);
          const count = bucket?.count ?? 0;
          const h = (count / max) * 100;
          return (
            <div key={score} className="flex h-full flex-col items-center justify-end">
              <div
                className="w-full rounded-t-sm bg-gradient-to-t from-amber-deep to-amber-hi opacity-90 transition-opacity hover:opacity-100"
                style={{ height: `${Math.max(2, h)}%` }}
                title={`${count} at ${score}/10`}
              />
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-10 gap-1.5 mt-1.5">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="text-center font-mono text-xs tnum text-text-dim">
            {i + 1}
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
