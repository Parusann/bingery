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
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        <button
          onClick={() => onGenre("")}
          className={cn(
            "shrink-0 inline-flex items-center min-h-[44px] px-3.5 py-2 rounded-full text-sm border",
            genre === ""
              ? "bg-amber text-bg border-amber"
              : "border-border text-text-muted hover:text-text hover:border-border-strong"
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
                "shrink-0 inline-flex items-center min-h-[44px] px-3.5 py-2 rounded-full text-sm border transition-colors",
                active
                  ? "border-transparent text-bg"
                  : "border-border text-text-muted hover:text-text hover:border-border-strong"
              )}
              style={active ? { background: genreColor(g) } : undefined}
            >
              {g}
            </button>
          );
        })}
      </div>
      <div className="flex items-center gap-2 text-sm">
        <span className="text-text-muted">Sort by</span>
        {sorts.map((s) => (
          <button
            key={s.key}
            onClick={() => onSort(s.key)}
            className={cn(
              "inline-flex items-center min-h-[44px] px-3 py-2 rounded-md",
              sort === s.key
                ? "text-text bg-white/[0.06]"
                : "text-text-muted hover:text-text"
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
