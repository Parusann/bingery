import type { WatchStatus } from "@/types/models";
import type { WatchStats } from "@/types/models";
import { cn } from "@/lib/cn";

// Status colors retuned to the dusty film-grade ramp (was raw Tailwind
// blue/green/amber/violet/red). Keys and labels are untouched — other files
// import STATUSES for both.
export const STATUSES: Array<{ key: WatchStatus; label: string; color: string }> = [
  { key: "watching", label: "Watching", color: "#7fa3d1" },
  { key: "completed", label: "Completed", color: "#9bc9ab" },
  { key: "plan_to_watch", label: "Plan to Watch", color: "#e0a068" },
  { key: "on_hold", label: "On Hold", color: "#ab8fd1" },
  { key: "dropped", label: "Dropped", color: "#c47a7a" },
];

interface Props {
  stats?: WatchStats;
  value: WatchStatus | null;
  onChange: (s: WatchStatus | null) => void;
}

export function StatusTabs({ stats, value, onChange }: Props) {
  const counts: Record<string, number> = stats
    ? (stats as unknown as Record<string, number>)
    : {};
  const total = STATUSES.reduce((n, s) => n + (counts[s.key] ?? 0), 0);
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 mb-6 scrollbar-none [mask-image:linear-gradient(to_right,black,black_calc(100%-40px),transparent)]">
      <button
        onClick={() => onChange(null)}
        className={cn(
          "shrink-0 min-h-[44px] px-4 py-2 rounded-pill text-sm border transition-colors",
          value === null
            ? "bg-gradient-to-b from-amber-hi to-amber text-bg border-amber-hi/60 font-semibold"
            : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
        )}
      >
        All <span className="ml-1 text-xs font-mono tnum opacity-70">{total}</span>
      </button>
      {STATUSES.map((s) => {
        const n = counts[s.key] ?? 0;
        const active = value === s.key;
        return (
          <button
            key={s.key}
            onClick={() => onChange(s.key)}
            className={cn(
              "shrink-0 min-h-[44px] px-4 py-2 rounded-pill text-sm border transition-colors",
              active
                ? "border-transparent text-bg font-semibold"
                : "border-border bg-surface text-text-muted hover:text-text hover:border-border-strong"
            )}
            style={active ? { background: s.color } : undefined}
          >
            {s.label}
            <span className="ml-1 text-xs font-mono tnum opacity-70">{n}</span>
          </button>
        );
      })}
    </div>
  );
}
