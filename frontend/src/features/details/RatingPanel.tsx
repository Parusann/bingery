import { useEffect, useState } from "react";
import type { AnimeDetail } from "@/types/models";
import { StarRating } from "@/design/StarRating";
import { Button } from "@/design/Button";
import { FAN_GENRES, genreColor } from "@/lib/genres";
import { cn } from "@/lib/cn";
import { useSubmitReview } from "@/hooks/useRatings";
import { useAuth } from "@/stores/auth";

export function RatingPanel({ anime }: { anime: AnimeDetail }) {
  const user = useAuth((s) => s.user);
  const [score, setScore] = useState(anime.user_rating?.score ?? 0);
  const [review, setReview] = useState(anime.user_rating?.review ?? "");
  const [fgs, setFgs] = useState<string[]>(anime.user_genre_votes ?? []);
  const [saved, setSaved] = useState(false);
  const submit = useSubmitReview(anime.id);

  useEffect(() => {
    setScore(anime.user_rating?.score ?? 0);
    setReview(anime.user_rating?.review ?? "");
    setFgs(anime.user_genre_votes ?? []);
  }, [anime.id]);

  if (!user) {
    return (
      <p className="text-sm text-text-muted">
        Sign in to rate, review, and vote on fan-genres.
      </p>
    );
  }

  const toggle = (g: string) =>
    setFgs((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : prev.length < 15 ? [...prev, g] : prev
    );

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm text-text-muted block mb-2">Your rating</label>
        <StarRating value={score} onChange={setScore} />
      </div>
      <div>
        <label className="text-sm text-text-muted block mb-2">
          Short review (optional)
        </label>
        <textarea
          value={review}
          onChange={(e) => {
            setReview(e.target.value);
            setSaved(false);
          }}
          placeholder="What did you think?"
          className="w-full min-h-[80px] px-3 py-2 rounded-lg bg-surface border border-border focus:border-border-strong outline-none text-sm font-sans"
        />
      </div>
      <div>
        <label className="text-sm text-text-muted block mb-2">
          Fan-genre votes <span className="text-text-dim">({fgs.length}/15)</span>
        </label>
        <div className="flex flex-wrap gap-2">
          {FAN_GENRES.map((g) => {
            const active = fgs.includes(g);
            return (
              <button
                key={g}
                onClick={() => toggle(g)}
                className={cn(
                  "px-3.5 py-2 rounded-full text-sm border transition-colors min-h-[44px] inline-flex items-center",
                  active
                    ? "border-transparent text-bg"
                    : "border-border text-text-muted hover:border-border-strong"
                )}
                style={active ? { background: genreColor(g) } : undefined}
              >
                {g}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button
          onClick={() =>
            submit
              .mutateAsync({ score, review, genres: fgs })
              .then(() => {
                setSaved(true);
                setTimeout(() => setSaved(false), 1800);
              })
          }
          loading={submit.isPending}
          disabled={score === 0}
        >
          {saved ? "Saved" : "Save rating"}
        </Button>
        {submit.isError ? (
          <span className="text-sm text-danger">
            {(submit.error as Error).message}
          </span>
        ) : null}
      </div>
    </div>
  );
}
