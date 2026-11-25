import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useNsfw } from "@/stores/nsfw";
import type { AnimeSummary } from "@/types/models";

export function useSearch(query: string, minChars = 2, delay = 250) {
  const visible = useNsfw((state) => state.visible);
  const [results, setResults] = useState<AnimeSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setResults([]);
    if (query.length < minChars) {
      setLoading(false);
      return;
    }
    setLoading(true);
    // Superseded requests must not overwrite newer results when their
    // responses arrive out of order.
    let cancelled = false;
    const id = setTimeout(() => {
      api
        .autocomplete(query)
        .then((r) => {
          if (!cancelled) setResults(r.results ?? []);
        })
        .catch(() => {
          if (!cancelled) setResults([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, delay);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [query, minChars, delay, visible]);

  return { results, loading };
}
