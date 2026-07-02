import { Fragment, useState } from "react";
import { Button } from "@/design/Button";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useActivity } from "@/hooks/useActivity";
import { ActivityEntry } from "./ActivityEntry";

// Relative day label for timeline dividers.
function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const dayStart = (x: Date) =>
    new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((dayStart(now) - dayStart(d)) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: d.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

export function ActivityPage() {
  const user = useAuth((s) => s.user);
  const [page, setPage] = useState(1);
  const q = useActivity(page, !!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <div className="font-mono text-micro uppercase text-amber mb-3">
          Timeline
        </div>
        <h1 className="font-display text-display mb-2">
          Sign in for your timeline
        </h1>
        <p className="text-text-muted">
          See every rating, status change, and collection add.
        </p>
      </div>
    );
  }

  // Insert a mono day divider whenever the calendar day changes.
  let lastDay = "";

  return (
    <div>
      <div className="mb-6">
        <div className="font-mono text-micro uppercase text-amber mb-2">
          Timeline
        </div>
        <h1 className="font-display text-display">Activity</h1>
      </div>
      <div className="relative max-w-3xl">
        {/* spine rail — nodes sit on top of it */}
        <div
          aria-hidden
          className="absolute left-4 top-2 bottom-2 w-px bg-border"
        />
        <div className="space-y-2">
          {q.isLoading ? (
            Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="flex gap-3 items-start">
                <Skeleton className="h-8 w-8 mt-2.5 shrink-0" rounded="md" />
                <Skeleton className="h-[76px] flex-1" rounded="lg" />
              </div>
            ))
          ) : q.data?.events.length ? (
            q.data.events.map((ev) => {
              const day = dayLabel(ev.created_at);
              const showDivider = day !== lastDay;
              lastDay = day;
              return (
                <Fragment key={ev.id}>
                  {showDivider ? (
                    <div className="relative pl-11 pt-4 pb-1 first:pt-0">
                      <span className="font-mono text-micro uppercase text-text-dim">
                        {day}
                      </span>
                    </div>
                  ) : null}
                  <ActivityEntry event={ev} />
                </Fragment>
              );
            })
          ) : (
            <div className="py-16 text-center">
              <div className="font-mono text-micro uppercase text-text-dim mb-3">
                Quiet in here
              </div>
              <p className="font-display italic text-title text-text-muted">
                No activity yet.
              </p>
            </div>
          )}
        </div>
      </div>
      {q.data && q.data.pages > 1 ? (
        <nav
          className="flex items-center gap-3 mt-6 max-w-3xl justify-center"
          aria-label="Pagination"
        >
          <Button
            size="sm"
            variant="glass"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="font-mono text-caption tnum text-text-muted">
            {q.data.page} / {q.data.pages}
          </span>
          <Button
            size="sm"
            variant="glass"
            disabled={page >= q.data.pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </nav>
      ) : null}
    </div>
  );
}
