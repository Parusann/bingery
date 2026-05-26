import type { ScheduleWeekEpisode } from "@/types/models";
import { formatWeekdayLong } from "./utils";

export function DayBanner({
  date,
  episodes,
  isToday,
}: {
  date: string;
  episodes: ScheduleWeekEpisode[];
  isToday: boolean;
}) {
  const isEmpty = episodes.length === 0;
  const watchlistCount = episodes.filter((e) => e.on_watchlist).length;
  const collage = episodes.slice(0, 3);
  const fullLabel = formatWeekdayLong(date);

  const wrapperCls = [
    "relative overflow-hidden rounded-[22px] border",
    isEmpty ? "h-[168px]" : "h-[232px]",
    isToday
      ? "border-peach/30 shadow-[0_30px_70px_-28px_rgba(244,182,144,0.25)]"
      : "border-line-2 shadow-[0_30px_70px_-32px_rgba(0,0,0,0.6)]",
    "bg-bg-elevated",
  ].join(" ");

  return (
    <section className={wrapperCls} aria-label={`Day banner ${date}`}>
      {!isEmpty && (
        <div className="absolute inset-0 grid grid-cols-3" aria-hidden>
          {collage.map((e, i) => (
            <div
              key={e.id}
              className="bg-cover bg-center"
              style={{
                backgroundImage: e.anime.image_url ? `url(${e.anime.image_url})` : undefined,
                filter: "saturate(1.05) brightness(0.85)",
                maskImage: maskFor(i, collage.length),
                WebkitMaskImage: maskFor(i, collage.length),
              }}
            />
          ))}
        </div>
      )}

      <div
        aria-hidden
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(10,7,16,0.20) 0%, rgba(10,7,16,0.65) 60%, rgba(10,7,16,0.92) 100%), linear-gradient(90deg, rgba(10,7,16,0.85) 0%, rgba(10,7,16,0.30) 45%, rgba(10,7,16,0.55) 100%)",
        }}
      />

      <div className="relative flex h-full flex-col justify-between p-7">
        <div className="flex items-center gap-3">
          {isToday && (
            <span className="inline-flex items-center gap-2 rounded-full bg-peach/10 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-peach">
              <span className="h-1.5 w-1.5 rounded-full bg-peach animate-pulse" />
              TODAY
            </span>
          )}
          <h2 className="font-display italic text-[52px] leading-none tracking-tight bg-gradient-to-b from-ink to-mute bg-clip-text text-transparent">
            {fullLabel}
          </h2>
        </div>

        {isEmpty ? (
          <p className="font-display italic text-[32px] text-ink-2">No releases</p>
        ) : (
          <div className="flex items-end justify-between">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[40px] text-peach">{episodes.length}</span>
              <span className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-mute">
                {episodes.length === 1 ? "episode" : "episodes"}
              </span>
            </div>
            {watchlistCount > 0 && (
              <span className="inline-flex items-center gap-2 rounded-full bg-gold/[0.08] border border-gold/[0.35] px-3 py-1 text-[11px] font-mono uppercase tracking-[0.18em] text-gold">
                ★ {watchlistCount} on your watchlist
              </span>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function maskFor(idx: number, total: number): string {
  if (total === 1) return "linear-gradient(90deg, #000 0%, #000 100%)";
  if (total === 2) {
    return idx === 0
      ? "linear-gradient(90deg, #000 70%, transparent 100%)"
      : "linear-gradient(90deg, transparent 0%, #000 30%)";
  }
  if (idx === 0) return "linear-gradient(90deg, #000 65%, transparent 100%)";
  if (idx === 1) return "linear-gradient(90deg, transparent 0%, #000 18%, #000 82%, transparent 100%)";
  return "linear-gradient(90deg, transparent 0%, #000 35%)";
}
