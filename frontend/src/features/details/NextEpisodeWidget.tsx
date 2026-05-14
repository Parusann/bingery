import { useAnimeEpisodes } from "@/hooks/useSchedule";
import type { Episode } from "@/types/models";

function formatRelative(iso: string): string {
  const target = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = target - now;
  if (diffMs <= 0) return "now";
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  if (hours < 24) {
    const mins = Math.floor((diffMs / (1000 * 60)) % 60);
    return `${hours}h ${mins}m`;
  }
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return `${days}d ${remHours}h`;
}

function Pill({
  episode,
  kind,
  airAt,
}: {
  episode: Episode;
  kind: "sub" | "dub";
  airAt: string;
}) {
  const tone =
    kind === "dub"
      ? "bg-violet-400/15 text-violet-300 border-violet-400/30"
      : "bg-amber/15 text-amber border-amber/30";
  return (
    <span
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm ${tone}`}
      title={airAt}
    >
      <span aria-hidden>📺</span>
      Episode {episode.episode_number} ({kind}) airs in {formatRelative(airAt)}
    </span>
  );
}

export function NextEpisodeWidget({ animeId }: { animeId: number }) {
  const q = useAnimeEpisodes(animeId);
  if (!q.data) return null;
  const subEp = q.data.next_sub;
  const dubEp = q.data.next_dub;
  if (!subEp && !dubEp) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-4">
      {subEp && subEp.air_date_sub ? (
        <Pill episode={subEp} kind="sub" airAt={subEp.air_date_sub} />
      ) : null}
      {dubEp && dubEp.air_date_dub ? (
        <Pill episode={dubEp} kind="dub" airAt={dubEp.air_date_dub} />
      ) : null}
    </div>
  );
}
