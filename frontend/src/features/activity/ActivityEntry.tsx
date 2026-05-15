import { Link } from "react-router-dom";
import type { ActivityEvent } from "@/types/models";

function label(ev: ActivityEvent): string {
  const title = ev.anime?.title_english ?? ev.anime?.title ?? "an anime";
  switch (ev.kind) {
    case "rating": {
      const score = (ev.meta.score as number | undefined) ?? null;
      return score ? `Rated ${title} · ${score}/10` : `Rated ${title}`;
    }
    case "watch_status": {
      const status = (ev.meta.status as string | undefined) ?? "updated";
      return `${status.replace(/_/g, " ")} · ${title}`;
    }
    case "favorite":
      return `Favorited ${title}`;
    case "collection_item":
      return `Added ${title} to collection`;
    case "collection_create":
      return `Started a new collection${
        ev.meta.title ? ` — ${ev.meta.title}` : ""
      }`;
    case "genre_vote":
      return `Voted ${ev.meta.genre as string} on ${title}`;
    case "dub_report": {
      const epNum = ev.meta.episode_number as number | undefined;
      const status = ev.meta.status as string | undefined;
      const tail =
        status === "accepted"
          ? " · accepted"
          : status === "rejected"
            ? " · rejected"
            : " · pending review";
      const epPart = epNum != null ? ` ep ${epNum}` : "";
      return `Reported dub date for ${title}${epPart}${tail}`;
    }
    default:
      return "Activity";
  }
}

export function ActivityEntry({ event }: { event: ActivityEvent }) {
  const body = (
    <div className="flex gap-3 items-center">
      {event.anime?.image_url ? (
        <img
          src={event.anime.image_url}
          alt=""
          className="w-10 h-14 rounded object-cover shrink-0"
        />
      ) : (
        <div className="w-10 h-14 rounded bg-white/5 shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate capitalize">{label(event)}</div>
        <div className="text-xs text-text-muted">
          {new Date(event.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
  return event.anime?.id ? (
    <Link
      to={`/anime/${event.anime.id}`}
      className="block p-3 rounded-lg border border-border bg-surface hover:border-border-strong transition-colors"
    >
      {body}
    </Link>
  ) : (
    <div className="p-3 rounded-lg border border-border bg-surface">{body}</div>
  );
}
