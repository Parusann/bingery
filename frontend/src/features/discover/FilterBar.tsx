import { FAN_GENRES, genreColor } from "@/lib/genres";
import { cn } from "@/lib/cn";

interface Props {
  genre: string;
  onGenre: (g: string) => void;
  sort: string;
  onSort: (s: string) => void;
}

const sorts: Array<{ key: string; label: string }> = [
  { key: "api_score", label: "API score" },
  { key: "community_score", label: "Community score" },
  { key: "year", label: "Year" },
  { key: "title", label: "Title" },
];

export function FilterBar({ genre, onGenre, sort, onSort }: Props) {
  return (
    <div className="flex flex-col gap-3 mb-6">
      {/* Genre rail — right edge fades to hint scrollability */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none [mask-image:linear-gradient(to_right,black,black_calc(100%-40px),transparent)]">
        <button
          onClick={() => onGenre("")}
          className={cn(
            "shrink-0 inline-flex items-center min-h-[44px] px-4 py-2 rounded-pill text-sm border transition-colors",
            genre === ""
              ? "bg-gradient-to-b from-amber-hi to-amber text-bg border-amber-hi/60 font-semibold shadow-[0_8px_24px_-10px_rgba(239,171,129,0.5)]"
              : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
          )}
        >
          All
        </button>
        {FAN_GENRES.map((g) => {
          const active = genre === g;
          return (
            <button
              key={g}
              onClick={() => onGenre(g)}
              className={cn(
                "shrink-0 inline-flex items-center min-h-[44px] px-4 py-2 rounded-pill text-sm border transition-colors",
                active
                  ? "border-transparent text-bg font-semibold"
                  : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
              )}
              style={active ? { background: genreColor(g) } : undefined}
            >
              {g}
            </button>
          );
        })}
      </div>
      {/* Sort — segmented control */}
      <div className="flex items-center gap-3 overflow-x-auto scrollbar-none">
        <span className="shrink-0 font-mono text-micro uppercase text-text-dim">
          Sort
        </span>
        <div className="inline-flex items-center rounded-pill border border-border bg-surface p-1">
          {sorts.map((s) => (
            <button
              key={s.key}
              onClick={() => onSort(s.key)}
              className={cn(
                "shrink-0 inline-flex items-center min-h-[36px] px-3.5 rounded-pill text-caption whitespace-nowrap transition-colors",
                sort === s.key
                  ? "bg-surface-strong text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]"
                  : "text-text-muted hover:text-text"
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
