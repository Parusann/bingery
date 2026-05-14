import { useState } from "react";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useSchedule } from "@/hooks/useSchedule";
import { ScheduleCalendar } from "./ScheduleCalendar";

type Kind = "sub" | "dub" | "both";

export function SchedulePage() {
  const user = useAuth((s) => s.user);
  const [kind, setKind] = useState<Kind>("sub");
  const q = useSchedule(7, kind);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in to see the schedule</h1>
        <p className="text-text-muted">
          Track sub and dub episode releases for shows you're following.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <h1 className="font-display text-4xl text-amber">Upcoming episodes</h1>
        <div className="flex gap-2 text-sm sm:ml-auto">
          {(["sub", "dub", "both"] as Kind[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={
                "px-3 py-1.5 rounded-md capitalize " +
                (kind === k
                  ? "bg-white/[0.08] text-text"
                  : "text-text-muted hover:text-text")
              }
            >
              {k}
            </button>
          ))}
        </div>
      </div>
      {q.isLoading || !q.data ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24" rounded="lg" />
          ))}
        </div>
      ) : (
        <ScheduleCalendar days={q.data.days} />
      )}
    </div>
  );
}
