import { Link } from "react-router-dom";
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
      className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50"
    >
      <div className="relative aspect-[2/3] w-10 shrink-0 overflow-hidden rounded bg-black/40">
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
        <h3 className="truncate text-sm font-semibold">
          {a.title_english ?? a.title}
        </h3>
        <div className="mt-0.5 flex items-center gap-2 text-xs">
          {statusMeta ? (
            <span style={{ color: statusMeta.color }}>{statusMeta.label}</span>
          ) : null}
          <span className="text-text-dim">
            ep {entry.episodes_watched}
            {total != null ? ` / ${total}` : ""}
          </span>
        </div>
      </div>
      {entry.score != null ? (
        <span className="shrink-0 font-mono text-xs text-amber">
          ★ {entry.score}
        </span>
      ) : (
        <span className="shrink-0 text-[10px] text-text-dim">unrated</span>
      )}
    </Link>
  );
}
