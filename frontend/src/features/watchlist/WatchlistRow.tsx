import { Link } from "react-router-dom";
import { Star } from "lucide-react";
import type { WatchEntry } from "@/types/models";
import { STATUSES } from "./StatusTabs";

/**
 * List-view row: small thumbnail, title, status, episode progress, and your
 * score. Denser than the poster card; used by the "List" view mode.
 */
export function WatchlistRow({ entry }: { entry: WatchEntry }) {
  const a = entry.anime;
  const statusMeta = STATUSES.find((s) => s.key === entry.status);
  const total = a.episodes ?? null;
  return (
    <Link
      to={`/anime/${a.id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-border-strong hover:bg-surface-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
    >
      <div className="relative aspect-[2/3] w-10 shrink-0 overflow-hidden rounded-sm bg-black/40">
        {a.image_url ? (
          <img
            src={a.image_url}
            alt={a.title}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-sm font-medium">
          {a.title_english ?? a.title}
        </h3>
        <div className="mt-0.5 flex items-center gap-2 text-xs">
          {statusMeta ? (
            <span className="inline-flex items-center gap-1.5" style={{ color: statusMeta.color }}>
              <span
                aria-hidden
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: statusMeta.color }}
              />
              {statusMeta.label}
            </span>
          ) : null}
          <span className="font-mono tnum text-text-dim">
            ep {entry.episodes_watched}
            {total != null ? ` / ${total}` : ""}
          </span>
        </div>
      </div>
      {entry.score != null ? (
        <span className="inline-flex items-center gap-1 shrink-0 font-mono text-xs tnum text-gold">
          <Star className="h-3 w-3" fill="currentColor" aria-hidden />
          {entry.score}
        </span>
      ) : (
        <span className="shrink-0 font-mono text-[10px] text-text-dim">unrated</span>
      )}
    </Link>
  );
}
