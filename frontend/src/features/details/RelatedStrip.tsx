import { Link } from "react-router-dom";
import { cn } from "@/lib/cn";
import type { RelatedEntry } from "@/types/api";

function releaseLabel(e: RelatedEntry): string {
  if (e.release_date) {
    const d = new Date(e.release_date);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString(undefined, { year: "numeric", month: "short" });
    }
  }
  return e.year ? String(e.year) : "TBA";
}

export function RelatedStrip({ related }: { related: RelatedEntry[] }) {
  // Nothing meaningful to show for a standalone title (just itself).
  if (related.length <= 1) return null;

  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl mb-4">Watch the rest in order!</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {related.map((e) => {
          const inner = (
            <>
              <div className="relative aspect-[2/3] bg-black/40 overflow-hidden">
                {e.image_url ? (
                  <img
                    src={e.image_url}
                    alt={e.title}
                    loading="lazy"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-text-dim text-xs">
                    No image
                  </div>
                )}
                {e.format ? (
                  <span className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/70 backdrop-blur-md text-[11px] font-medium text-text">
                    {e.format}
                  </span>
                ) : null}
                {e.is_current ? (
                  <span className="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-amber text-black text-[11px] font-semibold">
                    Current
                  </span>
                ) : null}
              </div>
              <div className="p-3">
                <h3 className="text-sm font-semibold line-clamp-2 mb-1">{e.title}</h3>
                <p className="text-xs text-text-muted tabular-nums">{releaseLabel(e)}</p>
              </div>
            </>
          );

          const cardClass = cn(
            "block rounded-lg overflow-hidden border bg-surface transition-colors",
            e.is_current
              ? "border-amber ring-2 ring-amber/50"
              : "border-border hover:border-border-strong"
          );

          // Current title and non-catalog entries are not links.
          if (e.id != null && !e.is_current) {
            return (
              <Link key={e.anilist_id} to={`/anime/${e.id}`} className={cardClass}>
                {inner}
              </Link>
            );
          }
          return (
            <div
              key={e.anilist_id}
              className={cn(cardClass, e.id == null && "opacity-90")}
            >
              {inner}
            </div>
          );
        })}
      </div>
    </section>
  );
}
