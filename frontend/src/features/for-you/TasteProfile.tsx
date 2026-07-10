import type { TasteProfile as Profile } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { genreColor } from "@/lib/genres";

export function TasteProfile({ profile }: { profile: Profile | null }) {
  if (!profile || !profile.top_genres.length) return null;
  return (
    <GlassCard tone="warm" className="p-6 mb-8">
      <div className="flex items-baseline justify-between gap-3 flex-wrap mb-4">
        <h2 className="font-display text-title">Your taste</h2>
        <div className="font-mono text-caption tnum text-text-muted">
          {profile.rating_count} ratings
          {profile.avg_score !== null
            ? ` · avg ${profile.avg_score.toFixed(1)}/10`
            : ""}
        </div>
      </div>
      <div className="space-y-2.5">
        {profile.top_genres.slice(0, 8).map((g) => {
          const w = Math.max(6, Math.round(g.weight * 100));
          const c = genreColor(g.genre);
          return (
            <div key={g.genre} className="flex items-center gap-3 text-sm">
              <div className="w-32 shrink-0 text-caption text-text-muted truncate">
                {g.genre}
              </div>
              <div className="flex-1 h-2 rounded-pill bg-surface overflow-hidden">
                <div
                  className="h-full rounded-pill"
                  style={{
                    width: `${w}%`,
                    background: `linear-gradient(90deg, ${c}99, ${c})`,
                  }}
                />
              </div>
              <div className="w-10 text-right font-mono text-caption tnum text-text-dim">
                {Math.round(g.weight * 100)}%
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
