import { useState } from "react";
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { Skeleton } from "@/design/Skeleton";
import { useCompare } from "@/hooks/useCompare";
import { UserPicker } from "./UserPicker";
import { TasteVenn } from "./TasteVenn";

export function ComparePage() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [submitted, setSubmitted] = useState<{ a: string; b: string } | null>(null);
  const q = useCompare(submitted?.a ?? "", submitted?.b ?? "", !!submitted);

  return (
    <div className="space-y-8 max-w-4xl">
      <h1 className="font-display text-4xl text-amber">Compare taste</h1>
      <UserPicker
        a={a}
        b={b}
        onA={setA}
        onB={setB}
        onSubmit={() => setSubmitted({ a: a.trim(), b: b.trim() })}
      />
      {q.isFetching ? (
        <Skeleton className="h-56" rounded="lg" />
      ) : q.data ? (
        <>
          <TasteVenn
            taste={q.data.taste}
            aLabel={q.data.user_a.display_name ?? q.data.user_a.username}
            bLabel={q.data.user_b.display_name ?? q.data.user_b.username}
          />
          <section>
            <h2 className="font-display text-2xl mb-4">Anime you both rated</h2>
            <AnimeGrid
              anime={q.data.taste.shared_anime}
              empty="No shared anime yet."
            />
          </section>
        </>
      ) : q.isError ? (
        <p className="text-danger">Couldn't compare. Check the usernames.</p>
      ) : null}
    </div>
  );
}
