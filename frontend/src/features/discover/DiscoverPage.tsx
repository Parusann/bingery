import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAnimeList } from "@/hooks/useAnimeList";
import { AnimeGrid } from "./AnimeGrid";
import { FilterBar } from "./FilterBar";
import { SearchAutocomplete } from "./SearchAutocomplete";

export function DiscoverPage() {
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const genre = params.get("genre") ?? "";
  const sort = params.get("sort") ?? "api_score";
  const [page, setPage] = useState(1);

  const { data, isLoading, isFetching } = useAnimeList({
    page,
    search,
    genre,
    sort,
  });

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
    setPage(1);
  };

  return (
    <div>
      <div className="flex flex-col md:flex-row gap-4 mb-6 md:mb-8 items-start md:items-end">
        <div>
          <div className="font-mono text-micro uppercase text-amber mb-2">Catalog</div>
          <h1 className="font-display text-display">Discover</h1>
        </div>
        <div className="flex-1 w-full md:ml-auto md:max-w-xl md:pb-1">
          <SearchAutocomplete
            onSubmit={(q) => update("q", q)}
          />
        </div>
      </div>
      <FilterBar
        genre={genre}
        onGenre={(g) => update("genre", g)}
        sort={sort}
        onSort={(s) => update("sort", s)}
      />
      <AnimeGrid anime={data?.anime ?? []} loading={isLoading} />
      {data && data.pages > 1 ? (
        <nav
          className="flex justify-center items-center gap-3 mt-10 text-sm"
          aria-label="Pagination"
        >
          <Button
            variant="glass"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="font-mono text-caption text-text-muted tnum">
            {data.page} / {data.pages}
          </span>
          <Button
            variant="glass"
            size="sm"
            disabled={page >= data.pages || isFetching}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </nav>
      ) : null}
    </div>
  );
}
