import { useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useAnimeList } from "@/hooks/useAnimeList";
import { LoadError } from "@/design/PageState";
import { AnimeGrid } from "./AnimeGrid";
import { FilterBar, SORTS } from "./FilterBar";
import { SearchAutocomplete } from "./SearchAutocomplete";

export function DiscoverPage() {
  const [params, setParams] = useSearchParams();
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const search = params.get("q")?.trim() ?? "";
  const genre = params.get("genre") ?? "";
  const sort = SORTS.find((option) => option.key === params.get("sort")) ?? SORTS[0];
  const requestedPage = Number(params.get("page"));
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const { data, isLoading, isError, refetch, isFetching } = useAnimeList({
    page, search, genre, sort: sort.key, order: sort.key === "title" ? "asc" : "desc",
  });
  const filtered = Boolean(genre || search || sort.key !== SORTS[0].key);
  const featureFirst = page === 1 && !search && !genre && sort.key === "api_score";
  const beyondLastPage = Boolean(data && page > Math.max(1, data.pages));

  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (key !== "page") next.delete("page");
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { preventScrollReset: true });
  }

  function resetFilters() {
    setParams({}, { preventScrollReset: true });
  }

  function changePage(next: number) {
    update("page", next === 1 ? "" : String(next));
    resultsHeading.current?.focus({ preventScroll: true });
    resultsHeading.current?.scrollIntoView?.({ block: "start" });
  }

  const heading = search ? `Results for “${search}”` : genre || "Browse titles";

  return (
    <div className="catalog">
      <header className="catalog-masthead">
        <h1>Discover</h1>
        <SearchAutocomplete value={search} onSubmit={(query) => update("q", query)} />
      </header>
      <section aria-labelledby="catalog-results">
        <div className="catalog-toolbar">
          <div className="catalog-summary">
            <h2 id="catalog-results" ref={resultsHeading} tabIndex={-1}>{heading}</h2>
            {data && !isError && (
              <span aria-live="polite" className="catalog-count">
                {data.total.toLocaleString()} {data.total === 1 ? "title" : "titles"}
              </span>
            )}
          </div>
          <FilterBar genre={genre} sort={sort.key}
            onGenre={(next) => update("genre", next)}
            onSort={(next) => update("sort", next === SORTS[0].key ? "" : next)}
            onReset={filtered ? resetFilters : undefined}
          />
        </div>
        {isError && !data ? (
          <LoadError title="The catalog couldn’t load." retry={() => refetch()} />
        ) : (
          <AnimeGrid anime={data?.anime ?? []} loading={isLoading} featureFirst={featureFirst}
            scoreSource={sort.key === "community_score" ? "community_score" : "api_score"}
            empty={
              <>
                <h3>{beyondLastPage ? "This page is empty." : filtered ? "No matching titles." : "The catalog is empty."}</h3>
                {beyondLastPage
                  ? <button type="button" className="catalog-action" onClick={() => changePage(1)}>Go to the first page</button>
                  : filtered && <button type="button" className="catalog-action" onClick={resetFilters}>Clear filters</button>}
              </>
            }
          />
        )}
        {data && !beyondLastPage && data.pages > 1 && (
          <nav className="catalog-pagination" aria-label="Pagination">
            <button type="button" disabled={page <= 1 || isFetching} onClick={() => changePage(page - 1)}>
              <ArrowLeft size={16} aria-hidden="true" /> Previous
            </button>
            <span>Page {page.toLocaleString()} of {data.pages.toLocaleString()}</span>
            <button type="button" disabled={page >= data.pages || isFetching} onClick={() => changePage(page + 1)}>
              Next <ArrowRight size={16} aria-hidden="true" />
            </button>
          </nav>
        )}
      </section>
    </div>
  );
}
