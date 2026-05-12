import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AnimeSummary } from "@/types/models";

export function useSearch(query: string, minChars = 2, delay = 250) {
  const [results, setResults] = useState<AnimeSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.length < minChars) {
      setResults([]);
      return;
    }
    setLoading(true);
    const id = setTimeout(() => {
      api
        .autocomplete(query)
        .then((r) => setResults(r.results ?? []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, delay);
    return () => clearTimeout(id);
  }, [query, minChars, delay]);

  return { results, loading };
}
