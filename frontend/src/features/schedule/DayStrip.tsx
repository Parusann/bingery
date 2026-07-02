import { ChevronLeft, ChevronRight } from "lucide-react";
import { formatWeekdayShort, dayNumber } from "./utils";

/**
 * Schedule day strip.
 *  - >=768px (md): single row [prev] [month/week label] [7 chips] [next].
 *  - <768px: stacks into two rows — row 1: month/week label + 44px chevrons;
 *    row 2: full-width 7-day chips with down-scaled internals.
 */
export function DayStrip({
  weekStart,
  todayIso,
  episodeCounts,
  onChipClick,
  onPrevWeek,
  onNextWeek,
}: {
  weekStart: string;
  todayIso: string;
  episodeCounts: Record<string, number>;
  onChipClick: (date: string) => void;
  onPrevWeek: () => void;
  onNextWeek: () => void;
}) {
  const dates: string[] = [];
  for (let i = 0; i < 7; i++) dates.push(shiftDay(weekStart, i));

  const monthLabel = monthOf(weekStart);
  const weekNumber = isoWeekOf(weekStart);

  const Chip = ({ d }: { d: string }) => {
    const isToday = d === todayIso;
    const count = episodeCounts[d] ?? 0;
    return (
      <button
        key={d}
        type="button"
        data-today={isToday}
        onClick={() => onChipClick(d)}
        className={[
          "relative flex flex-col items-center justify-center rounded-lg border px-1 py-1.5 md:px-2.5 md:py-2 transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
          isToday
            ? "border-peach/60 bg-gradient-to-b from-peach/20 to-peach/[0.06] shadow-[0_0_18px_-2px_rgba(239,171,129,0.45)]"
            : "border-line bg-row-bg hover:border-peach/30 hover:bg-peach/[0.06] hover:-translate-y-px",
        ].join(" ")}
      >
        <span className="font-mono text-[9px] md:text-[10px] uppercase tracking-[0.12em] md:tracking-[0.2em] text-mute">
          {formatWeekdayShort(d)}
        </span>
        <span
          className={
            isToday
              ? "font-display text-[18px] md:text-[24px] tnum bg-gradient-to-b from-peach to-peach-deep bg-clip-text text-transparent"
              : "font-display text-[18px] md:text-[24px] tnum text-ink"
          }
        >
          {dayNumber(d)}
        </span>
        {count > 0 && (
          <span className="absolute -top-1 right-0.5 md:right-1 font-mono text-[8px] md:text-[9px] tnum text-mute bg-bg-elevated rounded px-1">
            {count}
          </span>
        )}
        {isToday && (
          <span className="absolute -bottom-2 md:-bottom-3 font-mono text-[7px] md:text-[8px] uppercase tracking-[0.2em] text-peach">
            TODAY
          </span>
        )}
      </button>
    );
  };

  const PrevBtn = ({ big }: { big?: boolean }) => (
    <button
      type="button"
      aria-label="previous week"
      onClick={onPrevWeek}
      className={`grid ${big ? "h-11 w-11" : "h-9 w-9"} place-items-center rounded-lg border border-line text-ink-2 hover:text-ink hover:border-line-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60`}
    >
      <ChevronLeft className="h-4 w-4" aria-hidden />
    </button>
  );
  const NextBtn = ({ big }: { big?: boolean }) => (
    <button
      type="button"
      aria-label="next week"
      onClick={onNextWeek}
      className={`grid ${big ? "h-11 w-11" : "h-9 w-9"} place-items-center rounded-lg border border-line text-ink-2 hover:text-ink hover:border-line-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60`}
    >
      <ChevronRight className="h-4 w-4" aria-hidden />
    </button>
  );

  return (
    <div className="sticky top-14 md:top-0 z-30 -mx-4 px-4 py-3 md:py-3.5 bg-bg/80 md:bg-bg/70 backdrop-blur-xl md:backdrop-blur-md backdrop-saturate-150 border-b border-line">
      {/* ── Mobile: two stacked rows (md:hidden) ── */}
      <div className="md:hidden flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-peach">{monthLabel}</span>
            <span className="font-mono text-[11px] tnum text-mute">Week {weekNumber}</span>
          </div>
          <div className="flex items-center gap-2">
            <PrevBtn big />
            <NextBtn big />
          </div>
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {dates.map((d) => (
            <Chip key={d} d={d} />
          ))}
        </div>
      </div>

      {/* ── Desktop: single row (hidden md:flex) ── */}
      <div className="hidden md:flex items-center gap-4">
        <PrevBtn />
        <div className="flex flex-col items-end border-r border-line-2 pr-4">
          <span className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-peach">{monthLabel}</span>
          <span className="font-mono text-[11.5px] tnum text-mute">Week {weekNumber}</span>
        </div>
        <div className="grid flex-1 grid-cols-7 gap-2">
          {dates.map((d) => (
            <Chip key={d} d={d} />
          ))}
        </div>
        <NextBtn />
      </div>
    </div>
  );
}

function shiftDay(weekStart: string, days: number): string {
  const [y, m, d] = weekStart.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

function monthOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d))
    .toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" })
    .toUpperCase();
}

function isoWeekOf(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const dayNum = dt.getUTCDay() || 7;
  dt.setUTCDate(dt.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(dt.getUTCFullYear(), 0, 1));
  return Math.ceil((((dt.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}
