import { Star } from "lucide-react";

type Lang = "sub" | "dub" | "both";
const OPTIONS: Lang[] = ["sub", "dub", "both"];

export function FilterPills({
  lang,
  myShowsOnly,
  onLangChange,
  onMineToggle,
}: {
  lang: Lang;
  myShowsOnly: boolean;
  onLangChange: (v: Lang) => void;
  onMineToggle: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Segmented control — same pattern as Discover's sort switch */}
      <div className="inline-flex rounded-pill border border-line bg-row-bg p-1">
        {OPTIONS.map((opt) => {
          const active = opt === lang;
          return (
            <button
              key={opt}
              type="button"
              data-active={active}
              onClick={() => onLangChange(opt)}
              className={[
                "px-3.5 min-h-[36px] rounded-pill font-mono text-[11px] uppercase tracking-[0.16em] transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
                active ? "bg-peach/15 text-peach" : "text-ink-2 hover:text-ink",
              ].join(" ")}
            >
              {opt.toUpperCase()}
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={onMineToggle}
        data-active={myShowsOnly}
        className={[
          "inline-flex items-center gap-2 rounded-pill border px-4 min-h-[44px] font-mono text-[11px] uppercase tracking-[0.16em] transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
          myShowsOnly
            ? "border-gold/40 bg-gold/[0.08] text-gold"
            : "border-line bg-row-bg text-ink-2 hover:text-ink hover:border-line-2",
        ].join(" ")}
      >
        <Star className="h-3 w-3" fill={myShowsOnly ? "currentColor" : "none"} aria-hidden />
        My shows
      </button>
    </div>
  );
}
