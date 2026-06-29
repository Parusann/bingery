import { Link } from "react-router-dom";
import { Clock, Star, ChevronRight } from "lucide-react";
import type { ScheduleWeekEpisode } from "@/types/models";
import { Badge } from "./Badge";
import { EstimatedTag } from "./EstimatedTag";
import { formatLocalTime, formatLocalTzAbbr } from "./utils";

export function EpisodeRow({ episode }: { episode: ScheduleWeekEpisode }) {
  const highlighted = episode.on_watchlist;
  const title = episode.anime.title_english ?? episode.anime.title;

  const containerCls = [
    "grid grid-cols-[52px_1fr_auto] md:grid-cols-[60px_1fr_auto] gap-3 md:gap-[18px] items-center",
    "px-3 md:px-4 py-2.5 md:py-[10px] rounded-lg border transition-colors group",
    highlighted
      ? "bg-gold/[0.025] border-gold/20 hover:bg-gold/[0.055] hover:border-gold/[0.34]"
      : "bg-row-bg border-row-bd hover:bg-row-bg-hover hover:border-line-2",
  ].join(" ");

  const titleCls = [
    "font-display text-[17px] md:text-[21px] leading-tight tracking-tight line-clamp-1",
    highlighted ? "bg-gradient-to-b from-ink to-gold bg-clip-text text-transparent" : "text-ink",
  ].join(" ");

  return (
    <Link to={`/anime/${episode.anime_id}`} className={containerCls}>
      <div className="relative">
        {episode.anime.image_url ? (
          <img
            src={episode.anime.image_url}
            alt=""
            className="h-[70px] w-[52px] md:h-[80px] md:w-[60px] rounded-lg object-cover shadow-md"
          />
        ) : (
          <div className="h-[70px] w-[52px] md:h-[80px] md:w-[60px] rounded-lg bg-white/5" />
        )}
        {highlighted && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-gold text-[10px] text-bg">
            <Star className="h-2.5 w-2.5" fill="currentColor" />
          </span>
        )}
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={titleCls}>{title}</span>
          <span className="font-mono text-[10px] tracking-[0.14em] text-ink-2 rounded px-[6px] py-[2px] bg-white/5">
            EP {episode.episode_number}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-[12px] text-ink-2">
          <Clock className="h-3 w-3" />
          {episode.estimated ? (
            <>
              {/* Synthetic dub: the projected clock time is meaningless, so we
                  show "time TBD" rather than a fake-precise minute. */}
              <span className="text-mute">time TBD</span>
              <EstimatedTag />
            </>
          ) : (
            <>
              <span>{formatLocalTime(episode.air_time_utc)}</span>
              <span className="font-mono text-[10px] tracking-[0.08em] rounded px-[5px] py-[1px] bg-white/5 text-mute">
                {formatLocalTzAbbr()}
              </span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Badge type={episode.type} />
        <ChevronRight className="h-4 w-4 text-mute transition-transform group-hover:translate-x-[2px] group-hover:text-ink" />
      </div>
    </Link>
  );
}
