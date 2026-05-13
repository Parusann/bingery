import type { Season } from "@/types/models";
import { cn } from "@/lib/cn";

const SEASONS: Season[] = ["winter", "spring", "summer", "fall"];

interface Props {
  year: number;
  season: Season;
  onChange: (year: number, season: Season) => void;
}

export function SeasonPicker({ year, season, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2 items-center">
      <div className="flex gap-1">
        <button
          onClick={() => onChange(year - 1, season)}
          className="h-8 w-8 rounded-md border border-border text-text-muted hover:text-text hover:border-border-strong"
          aria-label="Previous year"
        >
          ‹
        </button>
        <div className="h-8 px-4 rounded-md bg-surface border border-border flex items-center font-mono tabular-nums">
          {year}
        </div>
        <button
          onClick={() => onChange(year + 1, season)}
          className="h-8 w-8 rounded-md border border-border text-text-muted hover:text-text hover:border-border-strong"
          aria-label="Next year"
        >
          ›
        </button>
      </div>
      <div className="flex gap-1">
        {SEASONS.map((s) => (
          <button
            key={s}
            onClick={() => onChange(year, s)}
            className={cn(
              "h-8 px-3 rounded-md border text-sm capitalize",
              season === s
                ? "bg-amber text-bg border-amber"
                : "border-border text-text-muted hover:text-text hover:border-border-strong"
            )}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
