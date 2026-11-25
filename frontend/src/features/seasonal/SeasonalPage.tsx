import { useAuth } from "@/stores/auth";
import { SignInPanel, LoadError } from "@/design/PageState";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { currentSeason, useSeasonal } from "@/hooks/useSeasonal";
import { SeasonPicker } from "./SeasonPicker";

export function SeasonalPage() {
  const initial = currentSeason();
  const [year, setYear] = useState(initial.year);
  const [season, setSeason] = useState(initial.season);
  const user = useAuth((s) => s.user);
  const q = useSeasonal(year, season, !!user);

  if (!user) return <SignInPanel section="Seasonal" title="Sign in to browse the season"
    description="Explore the anime lineup by season and year." />;

  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-center gap-4 mb-6">
        <h1 className="font-display text-4xl text-amber capitalize">
          {season} {year}
        </h1>
        <div className="md:ml-auto">
          <SeasonPicker
            year={year}
            season={season}
            onChange={(y, s) => {
              setYear(y);
              setSeason(s);
            }}
          />
        </div>
      </div>
      {q.isError && !q.data ? <LoadError title="This season couldn’t load." retry={() => q.refetch()} /> : <AnimeGrid
        anime={q.data?.anime ?? []}
        loading={q.isLoading}
        empty={
          <span>
            No anime found for this season.{" "}
            <Link to="/discover" className="text-amber hover:underline">
              Browse all anime →
            </Link>
          </span>
        }
      />}
    </div>
  );
}
