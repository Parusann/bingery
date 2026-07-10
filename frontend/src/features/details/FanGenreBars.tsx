import type { FanGenre } from "@/types/models";
import { genreColor } from "@/lib/genres";

export function FanGenreBars({ fanGenres }: { fanGenres: FanGenre[] }) {
  if (!fanGenres.length) return null;
  const max = fanGenres[0]?.votes || 1;
  return (
    <div className="space-y-2.5">
      {fanGenres.map((g) => {
        const w = (g.votes / max) * 100;
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
              {g.votes}
            </div>
          </div>
        );
      })}
    </div>
  );
}
