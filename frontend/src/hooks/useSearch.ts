import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AnimeSummary } from "@/types/models";

export function useSearch(query: string, minChars = 2, delay = 250) {
  const [results, setResults] = useState<AnimeSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.length < minChars) {
      setResults([]);
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
  }, [query, minChars, delay]);

  return { results, loading };
}
