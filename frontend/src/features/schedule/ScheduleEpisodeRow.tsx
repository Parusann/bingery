import { Link } from "react-router-dom";
import type { ScheduleEpisode } from "@/types/models";

function formatTime(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm} UTC`;
}

export function ScheduleEpisodeRow({ episode }: { episode: ScheduleEpisode }) {
  const title = episode.anime.title_english ?? episode.anime.title;
  const badgeClass =
    episode.kind === "dub"
      ? "bg-violet-400/15 text-violet-300"
      : "bg-amber/15 text-amber";
  return (
    <Link
      to={`/anime/${episode.anime.id}`}
      className="flex gap-3 p-3 rounded-lg border border-border bg-surface hover:border-border-strong transition-colors"
    >
      {episode.anime.image_url ? (
        <img
          src={episode.anime.image_url}
          alt=""
          className="w-[60px] h-[80px] rounded object-cover shrink-0"
        />
      ) : (
        <div className="w-[60px] h-[80px] rounded bg-white/5 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="font-medium line-clamp-2">{title}</div>
        <div className="text-sm text-text-muted">Episode {episode.episode_number}</div>
      </div>
      <div className="text-right flex flex-col items-end gap-1">
        <span className="tabular-nums font-mono text-sm">
          {formatTime(episode.air_at)}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded ${badgeClass} uppercase tracking-wider`}>
          {episode.kind}
        </span>
      </div>
    </Link>
  );
}
