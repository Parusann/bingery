import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";
import { useNsfw } from "@/stores/nsfw";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      // One retry for transient failures only — 4xx responses are
      // deterministic and retrying them just doubles the error latency.
      retry: (failureCount, error) =>
        failureCount < 1 &&
        !(error instanceof ApiError && error.status >= 400 && error.status < 500),
    },
    mutations: {
      retry: 0,
    },
  },
});

// The NSFW toggle changes what every list endpoint returns, but it isn't
// part of any query key — flush the cache when it flips so stale
// filtered/unfiltered pages can't linger.
useNsfw.subscribe((state, prev) => {
  if (state.visible !== prev.visible) {
    queryClient.invalidateQueries();
  }
});
