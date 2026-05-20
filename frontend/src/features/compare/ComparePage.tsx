import { useState } from "react";
import { Skeleton } from "@/design/Skeleton";
import { useAuth } from "@/stores/auth";
import { useCompare } from "@/hooks/useCompare";
import type { AnimeSummary } from "@/types/models";
import { AnimePicker } from "./AnimePicker";
import { CompareSummary } from "./CompareSummary";

// Compare two anime side-by-side. Replaces the older user-vs-user compare
// because there's only one demo user; this is also genuinely more useful —
// pick two titles, see scores, genre overlap, studios, your own ratings.

export function ComparePage() {
  const user = useAuth((s) => s.user);
  const [a, setA] = useState<AnimeSummary | null>(null);
  const [b, setB] = useState<AnimeSummary | null>(null);
  const q = useCompare(a?.id ?? null, b?.id ?? null);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">
          Sign in to compare anime
        </h1>
        <p className="text-text-muted">
          Pick two titles to see overlap, scores, and your own ratings.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-amber">Compare anime</h1>
        <p className="text-text-muted text-sm max-w-2xl">
          Pick any two anime to see them side-by-side: genres, scores,
          studios, and your own ratings. Shared genres get highlighted.
        </p>
      </header>

      <div className="grid sm:grid-cols-2 gap-4">
        <AnimePicker label="Anime A" value={a} onChange={setA} />
        <AnimePicker label="Anime B" value={b} onChange={setB} />
      </div>

      {a && b ? (
        q.isFetching && !q.data ? (
          <div className="grid sm:grid-cols-2 gap-4">
            <Skeleton className="h-72" rounded="lg" />
            <Skeleton className="h-72" rounded="lg" />
          </div>
        ) : q.data ? (
          <CompareSummary data={q.data} />
        ) : q.isError ? (
          <p className="text-danger text-sm">
            Couldn't load the comparison — try a different pair.
          </p>
        ) : null
      ) : (
        <p className="text-text-muted text-sm">
          Pick two anime above to start the comparison.
        </p>
      )}
    </div>
  );
}
