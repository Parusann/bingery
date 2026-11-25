import { ChevronDown, RotateCcw } from "lucide-react";
import { useCatalogGenres } from "@/hooks/useAnimeList";

export const SORTS = [
  { key: "api_score", label: "Top rated" },
  { key: "community_score", label: "Community score" },
  { key: "year", label: "Newest releases" },
  { key: "title", label: "Title (A–Z)" },
];

interface Props {
  genre: string;
  sort: string;
  onGenre: (genre: string) => void;
  onSort: (sort: string) => void;
  onReset?: () => void;
}

export function FilterBar({ genre, sort, onGenre, onSort, onReset }: Props) {
  const genres = useCatalogGenres();
  const available = genres.data ?? [];

  return (
    <div className="catalog-filters">
      <label className="catalog-select">
        <span>Genre</span>
        <select value={genre} onChange={(event) => onGenre(event.target.value)}>
          <option value="">All genres</option>
          {genre && !available.includes(genre) && <option>{genre}</option>}
          {available.map((name) => <option key={name}>{name}</option>)}
        </select>
        <ChevronDown size={14} aria-hidden="true" />
      </label>
      <label className="catalog-select">
        <span>Sort by</span>
        <select value={sort} onChange={(event) => onSort(event.target.value)}>
          {SORTS.map(({ key, label }) => <option key={key} value={key}>{label}</option>)}
        </select>
        <ChevronDown size={14} aria-hidden="true" />
      </label>
      {onReset && (
        <button type="button" className="catalog-reset" onClick={onReset}>
          <RotateCcw size={14} aria-hidden="true" /> Reset
        </button>
      )}
      {genres.isError && (
        <button type="button" className="catalog-reset" onClick={() => genres.refetch()}>
          Retry genre list
        </button>
      )}
    </div>
  );
}
