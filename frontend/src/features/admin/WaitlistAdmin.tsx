import { useState } from "react";
import { Badge } from "@/design/Badge";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { palette } from "@/design/tokens";
import { useAuth } from "@/stores/auth";
import {
  useApproveWaitlistEntry,
  useWaitlistAdmin,
} from "@/hooks/useWaitlistAdmin";
import type { WaitlistEntry, WaitlistStatus } from "@/types/models";

const STATUS_COLORS: Record<WaitlistStatus, string> = {
  pending: palette.amber,
  approved: palette.success,
  registered: palette.violet,
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function InviteCode({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — the code is still selectable */
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      title="Copy invite code"
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-border bg-surface font-mono text-xs text-text-muted transition-colors hover:text-text hover:border-border-strong"
    >
      {code}
      <span className="uppercase text-[10px] tracking-wide">
        {copied ? "copied" : "copy"}
      </span>
    </button>
  );
}

function EntryRow({ entry }: { entry: WaitlistEntry }) {
  const approve = useApproveWaitlistEntry();

  return (
    <GlassCard className="p-4">
      <div className="flex flex-col md:flex-row md:items-center gap-3">
        <div className="grow space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-display text-lg">{entry.email}</span>
            <Badge color={STATUS_COLORS[entry.status]}>{entry.status}</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
            <span>Joined {formatDate(entry.created_at)}</span>
            {entry.approved_at ? (
              <>
                <span>·</span>
                <span>Approved {formatDate(entry.approved_at)}</span>
              </>
            ) : null}
            {entry.code_used_at ? (
              <>
                <span>·</span>
                <span>Registered {formatDate(entry.code_used_at)}</span>
              </>
            ) : null}
          </div>
          {entry.invite_code ? <InviteCode code={entry.invite_code} /> : null}
          {approve.isError ? (
            <p className="text-sm text-danger">
              {(approve.error as Error).message}
            </p>
          ) : null}
        </div>
        {entry.status === "pending" ? (
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => approve.mutate(entry.id)}
            loading={approve.isPending}
          >
            Approve
          </Button>
        ) : null}
      </div>
    </GlassCard>
  );
}

export function WaitlistAdmin() {
  const user = useAuth((s) => s.user);
  const q = useWaitlistAdmin(!!user?.is_owner);

  if (!user || !user.is_owner) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Not authorized</h1>
        <p className="text-text-muted">This page is for the app owner only.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl text-amber">Waitlist</h1>

      {q.isError ? (
        <p className="text-sm text-danger">{(q.error as Error).message}</p>
      ) : q.isLoading || !q.data ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" rounded="lg" />
          ))}
        </div>
      ) : q.data.entries.length === 0 ? (
        <p className="text-text-muted">The waitlist is empty.</p>
      ) : (
        <div className="space-y-3">
          {q.data.entries.map((e) => (
            <EntryRow key={e.id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}
