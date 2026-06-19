import type {
  WatchEntry,
  WatchStatus,
  WatchStats,
  GenreMatchMode,
  WatchlistSort,
} from "@/types/models";

export interface WatchlistFilterOpts {
  status: WatchStatus | null;
  q: string;
  genres: string[];
  genreMode: GenreMatchMode;
  favoritesOnly: boolean;
  sort: WatchlistSort;
}

/** Every genre name on an entry: the anime's official genres + the user's fan tags. */
function entryGenreNames(entry: WatchEntry): string[] {
  const official = (entry.anime.official_genres ?? []).map((g) => g.name);
  const fan = entry.genres ?? [];
  return [...official, ...fan];
}

export function filterAndSortEntries(
  entries: WatchEntry[],
  opts: WatchlistFilterOpts
): WatchEntry[] {
  const q = opts.q.trim().toLowerCase();
  const wanted = opts.genres.map((g) => g.toLowerCase());

  const filtered = entries.filter((e) => {
    if (opts.status && e.status !== opts.status) return false;
    if (opts.favoritesOnly && !e.is_favorite) return false;

    if (q) {
      const t = e.anime.title?.toLowerCase() ?? "";
      const te = e.anime.title_english?.toLowerCase() ?? "";
      if (!t.includes(q) && !te.includes(q)) return false;
    }

    if (wanted.length) {
      const have = new Set(entryGenreNames(e).map((g) => g.toLowerCase()));
      if (opts.genreMode === "all") {
        if (!wanted.every((g) => have.has(g))) return false;
      } else if (!wanted.some((g) => have.has(g))) {
        return false;
      }
    }
    return true;
  });

  const sorted = [...filtered];
  sorted.sort((a, b) => {
    switch (opts.sort) {
      case "title": {
        const ta = (a.anime.title_english ?? a.anime.title ?? "").toLowerCase();
        const tb = (b.anime.title_english ?? b.anime.title ?? "").toLowerCase();
        return ta.localeCompare(tb);
      }
      case "created":
        return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      case "score": {
        const sa = a.score ?? -1;
        const sb = b.score ?? -1;
        if (sb !== sa) return sb - sa;
        return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");
      }
      case "updated":
      default:
        return (b.updated_at ?? "").localeCompare(a.updated_at ?? "");
    }
  });
  return sorted;
}

export function deriveGenreOptions(entries: WatchEntry[]): string[] {
  const set = new Set<string>();
  for (const e of entries) for (const g of entryGenreNames(e)) set.add(g);
  return [...set].sort((a, b) => a.localeCompare(b));
}

export function deriveStatusCounts(entries: WatchEntry[]): WatchStats {
  const counts: WatchStats = {
    watching: 0,
    completed: 0,
    plan_to_watch: 0,
    on_hold: 0,
    dropped: 0,
    favorites: 0,
  };
  for (const e of entries) {
    if (e.status in counts) counts[e.status] += 1;
    if (e.is_favorite) counts.favorites += 1;
  }
  return counts;
}
