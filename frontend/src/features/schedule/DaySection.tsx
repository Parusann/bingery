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
    </section>
  );
}
