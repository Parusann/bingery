import { Tv } from "lucide-react";
import { useAnimeEpisodes } from "@/hooks/useSchedule";
import { EstimatedTag } from "@/features/schedule/EstimatedTag";
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

function formatApproxDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function Pill({
  episode,
  kind,
  airAt,
  estimated = false,
}: {
  episode: Episode;
  kind: "sub" | "dub";
  airAt: string;
  estimated?: boolean;
}) {
  // sub = amber (the house accent), dub = sage — matching the schedule's
  // sub/dub badge language everywhere episodes appear.
  const tone =
    kind === "dub"
      ? "bg-sage-bg text-sage border-sage-bd"
      : "bg-amber/[0.12] text-amber-hi border-amber/30";
  // Estimated dub: avoid a fake live countdown off a projected time — show an
  // approximate date instead so the precision matches what we actually know.
  const label = estimated
    ? `Episode ${episode.episode_number} (${kind}) expected ~${formatApproxDate(airAt)}`
    : `Episode ${episode.episode_number} (${kind}) airs in ${formatRelative(airAt)}`;
  return (
    <span
      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-pill border text-sm tnum ${tone}`}
      title={airAt}
    >
      <Tv aria-hidden className="w-3.5 h-3.5 shrink-0" />
      {label}
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
    <div className="flex flex-wrap items-center gap-2 mt-4">
      {subEp && subEp.air_date_sub ? (
        <Pill episode={subEp} kind="sub" airAt={subEp.air_date_sub} />
      ) : null}
      {dubEp && dubEp.air_date_dub ? (
        <span className="inline-flex items-center gap-2">
          <Pill
            episode={dubEp}
            kind="dub"
            airAt={dubEp.air_date_dub}
            estimated={Boolean(dubEp.dub_estimated)}
          />
          {dubEp.dub_estimated ? <EstimatedTag /> : null}
        </span>
      ) : null}
    </div>
  );
}
