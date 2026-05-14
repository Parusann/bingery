import type { ScheduleDay } from "@/types/models";
import { ScheduleEpisodeRow } from "./ScheduleEpisodeRow";

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

export function ScheduleCalendar({ days }: { days: ScheduleDay[] }) {
  return (
    <div className="space-y-6">
      {days.map((day) => (
        <section key={day.date}>
          <h2 className="font-display text-xl mb-2">{formatDate(day.date)}</h2>
          {day.episodes.length === 0 ? (
            <p className="text-text-muted text-sm">No releases scheduled.</p>
          ) : (
            <div className="space-y-2">
              {day.episodes.map((ep) => (
                <ScheduleEpisodeRow key={`${ep.id}-${ep.kind}`} episode={ep} />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
