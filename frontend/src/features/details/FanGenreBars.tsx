import type { FanGenre } from "@/types/models";
import { genreColor } from "@/lib/genres";

export function FanGenreBars({ fanGenres }: { fanGenres: FanGenre[] }) {
  if (!fanGenres.length) return null;
  const max = fanGenres[0]?.votes || 1;
  return (
    <div className="space-y-2">
      {fanGenres.map((g) => {
        const w = (g.votes / max) * 100;
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
              {g.votes}
            </div>
          </div>
        );
      })}
    </div>
  );
}
