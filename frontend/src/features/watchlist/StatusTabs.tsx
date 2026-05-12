import type { WatchStatus } from "@/types/models";
import type { WatchStats } from "@/types/models";
import { cn } from "@/lib/cn";

export const STATUSES: Array<{ key: WatchStatus; label: string; color: string }> = [
  { key: "watching", label: "Watching", color: "#3b82f6" },
  { key: "completed", label: "Completed", color: "#22c55e" },
  { key: "plan_to_watch", label: "Plan to Watch", color: "#f59e0b" },
  { key: "on_hold", label: "On Hold", color: "#8b5cf6" },
  { key: "dropped", label: "Dropped", color: "#ef4444" },
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
    <div className="flex gap-2 overflow-x-auto pb-1 mb-6">
      <button
        onClick={() => onChange(null)}
        className={cn(
          "shrink-0 px-4 py-2 rounded-full text-sm border",
          value === null
            ? "bg-amber text-bg border-amber"
            : "border-border text-text-muted hover:text-text hover:border-border-strong"
        )}
      >
        All <span className="ml-1 text-xs tabular-nums opacity-70">{total}</span>
      </button>
      {STATUSES.map((s) => {
        const n = counts[s.key] ?? 0;
        const active = value === s.key;
        return (
          <button
            key={s.key}
            onClick={() => onChange(s.key)}
            className={cn(
              "shrink-0 px-4 py-2 rounded-full text-sm border transition-colors",
              active
                ? "border-transparent text-bg"
                : "border-border text-text-muted hover:text-text hover:border-border-strong"
            )}
            style={active ? { background: s.color } : undefined}
          >
            {s.label}
            <span className="ml-1 text-xs tabular-nums opacity-70">{n}</span>
          </button>
        );
      })}
    </div>
  );
}
