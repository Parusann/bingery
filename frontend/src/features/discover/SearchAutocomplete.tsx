import { useEffect, useId, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Search, X } from "lucide-react";
import { useSearch } from "@/hooks/useSearch";

interface Props {
  value: string;
  onSubmit: (query: string) => void;
}

export function SearchAutocomplete({ value, onSubmit }: Props) {
  const [draft, setDraft] = useState(value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const listId = useId();
  const query = draft.trim();
  const { results, loading } = useSearch(open ? query : "");
  const showList = open && query.length >= 2;
  const matches = showList && !loading ? results : [];
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setDraft(value);
    setOpen(false);
    setActive(-1);
  }, [value]);

  useEffect(() => {
    if (location.hash === "#catalog-search") input.current?.focus();
  }, [location.hash, location.key]);

  useEffect(() => {
    if (active >= 0) list.current?.children[active]?.scrollIntoView?.({ block: "nearest" });
  }, [active]);

  function submit() {
    setOpen(false);
    setActive(-1);
    if (matches[active]) {
      navigate(`/anime/${matches[active].id}`);
    } else {
      setDraft(query);
      onSubmit(query);
    }
  }

  return (
    <form
      className="catalog-search"
      role="search"
      aria-label="Catalog search"
      onSubmit={(event) => { event.preventDefault(); submit(); }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
          setActive(-1);
        }
      }}
    >
      <div className="catalog-search__field">
        <Search size={19} aria-hidden="true" />
        <input
          ref={input}
          id="catalog-search"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={showList ? listId : undefined}
          aria-activedescendant={matches[active] ? `${listId}-${active}` : undefined}
          aria-label="Search anime"
          autoComplete="off"
          enterKeyHint="search"
          placeholder="Search anime…"
          value={draft}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setDraft(event.target.value);
            setActive(-1);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return;
            if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
              setActive(-1);
            }
            if (query.length >= 2 && ["ArrowDown", "ArrowUp"].includes(event.key)) {
              event.preventDefault();
              setOpen(true);
              if (matches.length) {
                setActive((previous) => event.key === "ArrowDown"
                  ? Math.min(previous + 1, matches.length - 1)
                  : previous < 0 ? matches.length - 1 : Math.max(previous - 1, -1));
              }
            }
          }}
        />
        {draft && (
          <button
            type="button"
            aria-label="Clear search"
            onClick={() => {
              setDraft(""); setActive(-1); input.current?.focus(); setOpen(false);
              if (value) onSubmit("");
            }}
          >
            <X size={16} aria-hidden="true" />
          </button>
        )}
        <button type="submit" aria-label="Search catalog" className="catalog-search__submit">
          <ArrowRight size={19} aria-hidden="true" />
        </button>
      </div>
      {showList && (
        <div className="catalog-search__popup">
          {matches.length === 0 && (
            <p role="status">{loading ? "Searching…" : "Press Enter to search the catalog."}</p>
          )}
          <ul ref={list} id={listId} role="listbox" aria-label="Suggested titles">
            {matches.map((anime, index) => (
              <li
                key={anime.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={active === index}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => { setOpen(false); navigate(`/anime/${anime.id}`); }}
              >
                <div className="catalog-search__poster">
                  {anime.image_url && <img src={anime.image_url} alt="" />}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{anime.title_english || anime.title}</div>
                  <div className="text-xs text-text-muted">
                    {[anime.year, anime.episodes ? `${anime.episodes} ep` : null].filter(Boolean).join(" · ")}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
