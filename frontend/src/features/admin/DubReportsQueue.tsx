import { useState } from "react";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import {
  useDubReports,
  useUpdateDubReport,
} from "@/hooks/useDubReports";
import type { DubReport, DubReportStatus } from "@/types/models";

const ADMIN_USER_ID = 1;
const STATUSES: DubReportStatus[] = ["pending", "accepted", "rejected"];

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function ReportRow({ report }: { report: DubReport }) {
  const update = useUpdateDubReport();
  const accept = () => update.mutate({ id: report.id, body: { status: "accepted" } });
  const reject = () => update.mutate({ id: report.id, body: { status: "rejected" } });

  return (
    <GlassCard className="p-4">
      <div className="flex flex-col md:flex-row md:items-center gap-3">
        <div className="grow space-y-1">
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <span>Episode #{report.episode_id}</span>
            <span>·</span>
            <span>by user #{report.submitted_by}</span>
            <span>·</span>
            <span>{formatDateTime(report.created_at)}</span>
          </div>
          <div className="font-display text-lg">
            Dub airs: {formatDateTime(report.air_date)}
          </div>
          {report.note ? (
            <p className="text-text-muted text-sm">“{report.note}”</p>
          ) : null}
          <div className="text-xs text-text-muted">
            Status: <span className="capitalize">{report.status}</span>
          </div>
        </div>
        {report.status === "pending" ? (
          <div className="flex gap-2">
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={accept}
              loading={update.isPending}
            >
              Accept
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={reject}
              loading={update.isPending}
            >
              Reject
            </Button>
          </div>
        ) : null}
      </div>
    </GlassCard>
  );
}

export function DubReportsQueue() {
  const user = useAuth((s) => s.user);
  const [status, setStatus] = useState<DubReportStatus>("pending");
  const q = useDubReports(status, !!user && user.id === ADMIN_USER_ID);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in required</h1>
        <p className="text-text-muted">Admin moderation lives behind auth.</p>
      </div>
    );
  }
  if (user.id !== ADMIN_USER_ID) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Admins only</h1>
        <p className="text-text-muted">
          This page is restricted to the moderation team.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <h1 className="font-display text-4xl text-amber">Dub-report queue</h1>
        <div className="flex gap-2 text-sm sm:ml-auto">
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatus(s)}
              className={
                "px-3 py-1.5 rounded-md capitalize " +
                (status === s
                  ? "bg-white/[0.08] text-text"
                  : "text-text-muted hover:text-text")
              }
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {q.isLoading || !q.data ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" rounded="lg" />
          ))}
        </div>
      ) : q.data.reports.length === 0 ? (
        <p className="text-text-muted">No {status} reports.</p>
      ) : (
        <div className="space-y-3">
          {q.data.reports.map((r) => (
            <ReportRow key={r.id} report={r} />
          ))}
        </div>
      )}
    </div>
  );
}
