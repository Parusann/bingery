import type { TasteProfile as Profile } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { genreColor } from "@/lib/genres";

export function TasteProfile({ profile }: { profile: Profile | null }) {
  if (!profile || !profile.top_genres.length) return null;
  return (
    <GlassCard tone="warm" className="p-6 mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-2xl">Your taste</h2>
        <div className="text-sm text-text-muted tabular-nums">
          {profile.rating_count} ratings
          {profile.avg_score !== null
            ? ` · avg ${profile.avg_score.toFixed(1)}/10`
            : ""}
        </div>
      </div>
      <div className="space-y-2">
        {profile.top_genres.slice(0, 8).map((g) => {
          const w = Math.max(6, Math.round(g.weight * 100));
          const c = genreColor(g.genre);
          return (
            <div key={g.genre} className="flex items-center gap-3 text-sm">
              <div className="w-32 shrink-0 text-text-muted">{g.genre}</div>
              <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${w}%`, background: c }}
                />
              </div>
              <div className="w-10 text-right font-mono text-text-muted tabular-nums">
                {Math.round(g.weight * 100)}%
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
