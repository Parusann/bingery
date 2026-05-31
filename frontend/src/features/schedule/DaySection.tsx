import type { ScheduleWeekEpisode } from "@/types/models";
import { DayBanner } from "./DayBanner";
import { EpisodeRow } from "./EpisodeRow";

export function DaySection({
  date,
  episodes,
  isToday,
  myShowsOnly,
}: {
  date: string;
  episodes: ScheduleWeekEpisode[];
  isToday: boolean;
  myShowsOnly: boolean;
}) {
  const watchlist = episodes.filter((e) => e.on_watchlist);
  const others = myShowsOnly ? [] : episodes.filter((e) => !e.on_watchlist);

  return (
    <section id={`day-${date}`} className="space-y-4">
      <DayBanner date={date} episodes={episodes} isToday={isToday} />
      {watchlist.length > 0 && (
        <div className="space-y-2 rounded-2xl border border-gold/20 bg-gold/[0.025] p-5">
          {watchlist.map((e) => (
            <EpisodeRow key={`w-${e.id}-${e.type}`} episode={e} />
          ))}
        </div>
      )}
      {watchlist.length > 0 && others.length > 0 && (
        <div className="h-px bg-line" />
      )}
      {others.length > 0 && (
        <div className="space-y-2">
          {others.map((e) => (
            <EpisodeRow key={`o-${e.id}-${e.type}`} episode={e} />
          ))}
        </div>
      )}
      <div className="flex justify-center pt-2">
        <button
          type="button"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="inline-flex items-center gap-2 rounded-full border border-peach/45 bg-peach/15 px-5 py-2 text-xs font-mono uppercase tracking-[0.2em] text-peach shadow-[0_8px_24px_-12px_rgba(244,182,144,0.5)] transition-all hover:gap-3 hover:border-peach/70 hover:bg-peach/25"
          aria-label="Back to top of schedule"
          title="Back to top"
        >
          <span aria-hidden="true">↑</span> Back to top
        </button>
      </div>
    </section>
  );
}
