import { useState } from "react";
import { Button } from "@/design/Button";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useActivity } from "@/hooks/useActivity";
import { ActivityEntry } from "./ActivityEntry";

export function ActivityPage() {
  const user = useAuth((s) => s.user);
  const [page, setPage] = useState(1);
  const q = useActivity(page, !!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in for your timeline</h1>
        <p className="text-text-muted">
          See every rating, status change, and collection add.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-6">Activity</h1>
      <div className="space-y-2 max-w-3xl">
        {q.isLoading ? (
          Array.from({ length: 10 }).map((_, i) => (
            <Skeleton key={i} className="h-20" rounded="lg" />
          ))
        ) : q.data?.events.length ? (
          q.data.events.map((ev) => <ActivityEntry key={ev.id} event={ev} />)
        ) : (
          <p className="text-text-muted">No activity yet.</p>
        )}
      </div>
      {q.data && q.data.pages > 1 ? (
        <div className="flex items-center gap-3 mt-6 max-w-3xl justify-center">
          <Button
            size="sm"
            variant="ghost"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="text-sm text-text-muted tabular-nums">
            {q.data.page} / {q.data.pages}
          </span>
          <Button
            size="sm"
            variant="ghost"
            disabled={page >= q.data.pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
