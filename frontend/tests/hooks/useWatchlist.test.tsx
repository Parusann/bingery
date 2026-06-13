import { describe, expect, it, vi, afterEach } from "vitest";
import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWatchlist } from "@/hooks/useWatchlist";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
);

const EMPTY = { entries: [], total: 0, page: 1, pages: 0 };

describe("useWatchlist auth gating", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useAuth.setState({ user: null, status: "idle" });
  });

  it("does not fetch when signed out", async () => {
    useAuth.setState({ user: null, status: "idle" });
    const spy = vi.spyOn(api, "getWatchlist").mockResolvedValue(EMPTY as never);
    renderHook(() => useWatchlist(), { wrapper });
    await new Promise((r) => setTimeout(r, 50));
    expect(spy).not.toHaveBeenCalled();
  });

  it("fetches when signed in", async () => {
    useAuth.setState({
      user: {
        id: 1,
        email: "a@b.c",
        username: "u",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "",
      },
      status: "authenticated",
    });
    const spy = vi.spyOn(api, "getWatchlist").mockResolvedValue(EMPTY as never);
    renderHook(() => useWatchlist(), { wrapper });
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });
});
