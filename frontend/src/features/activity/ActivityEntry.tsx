import { Link } from "react-router-dom";
import { FolderPlus, Heart, ListPlus, Megaphone, Play, Star, Tag } from "lucide-react";
import type { ActivityEvent } from "@/types/models";

function label(ev: ActivityEvent): string {
  const title = ev.anime?.title_english ?? ev.anime?.title ?? "an anime";
  switch (ev.kind) {
    case "rating":
      // Score renders as a gold chip on the row, not inside the sentence.
      return `Rated ${title}`;
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

// Timeline node + card. The icon chip sits ON the page's spine rail (it gets
// an opaque backing so the rail passes behind it); gold = stars/favorites,
// amber = watching, violet = collections, sage = votes/reports.
const KIND_ICONS: Record<
  string,
  { Icon: typeof Star; color: string; bg: string }
> = {
  rating: { Icon: Star, color: "#f4cf90", bg: "rgba(244,207,144,0.12)" },
  favorite: { Icon: Heart, color: "#f4cf90", bg: "rgba(244,207,144,0.12)" },
  watch_status: { Icon: Play, color: "#efab81", bg: "rgba(239,171,129,0.12)" },
  collection_item: { Icon: ListPlus, color: "#b89ac4", bg: "rgba(184,154,196,0.14)" },
  collection_create: { Icon: FolderPlus, color: "#b89ac4", bg: "rgba(184,154,196,0.14)" },
  genre_vote: { Icon: Tag, color: "#9BB8A8", bg: "rgba(155,184,168,0.14)" },
  dub_report: { Icon: Megaphone, color: "#9BB8A8", bg: "rgba(155,184,168,0.14)" },
};

export function ActivityEntry({ event }: { event: ActivityEvent }) {
  const kind = KIND_ICONS[event.kind] ?? KIND_ICONS.watch_status;
  const score =
    event.kind === "rating"
      ? ((event.meta.score as number | undefined) ?? null)
      : null;
  const time = new Date(event.created_at).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  const card = (
    <div className="flex gap-3 items-center">
      {event.anime?.image_url ? (
        <img
          src={event.anime.image_url}
          alt=""
          className="w-10 h-14 rounded-sm object-cover shrink-0"
        />
      ) : (
        <div className="w-10 h-14 rounded-sm bg-surface shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate capitalize">{label(event)}</div>
        <div
          className="font-mono text-xs tnum text-text-dim mt-0.5"
          title={new Date(event.created_at).toLocaleString()}
        >
          {time}
        </div>
      </div>
      {score != null ? (
        <span className="inline-flex items-center gap-1 shrink-0 rounded-md border border-gold-bd bg-gold/[0.08] px-2 py-0.5 font-mono text-xs tnum text-gold">
          <Star className="h-3 w-3" fill="currentColor" aria-hidden />
          {score}/10
        </span>
      ) : null}
    </div>
  );

  return (
    <div className="relative flex gap-3 items-start">
      {/* node — opaque backing so the rail passes behind it */}
      <span aria-hidden className="relative z-10 grid place-items-center h-8 w-8 rounded-md shrink-0 mt-2.5 bg-bg">
        <span
          className="absolute inset-0 rounded-md border border-border"
          style={{ background: kind.bg }}
        />
        <kind.Icon className="relative h-4 w-4" style={{ color: kind.color }} />
      </span>
      {event.anime?.id ? (
        <Link
          to={`/anime/${event.anime.id}`}
          className="flex-1 min-w-0 p-3 rounded-lg border border-border bg-surface transition-colors hover:border-border-strong hover:bg-surface-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          {card}
        </Link>
      ) : (
        <div className="flex-1 min-w-0 p-3 rounded-lg border border-border bg-surface">
          {card}
        </div>
      )}
    </div>
  );
}
