import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSearch } from "@/hooks/useSearch";
import { api } from "@/lib/api";

describe("useSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("ignores stale responses that resolve after a newer query", async () => {
    const resolvers: Record<string, (v: unknown) => void> = {};
    vi.spyOn(api, "autocomplete").mockImplementation(
      ((q: string) =>
        new Promise((resolve) => {
          resolvers[q] = resolve;
        })) as never
    );

    const { result, rerender } = renderHook(({ q }) => useSearch(q), {
      initialProps: { q: "ab" },
    });
    act(() => {
      vi.advanceTimersByTime(250); // fire the "ab" request
    });
    rerender({ q: "abc" });
    act(() => {
      vi.advanceTimersByTime(250); // fire the "abc" request
    });

    // The newer request resolves first; the stale one lands afterwards.
    await act(async () => {
      resolvers["abc"]({ results: [{ id: 2, title: "new" }] });
    });
    await act(async () => {
      resolvers["ab"]({ results: [{ id: 1, title: "stale" }] });
    });

    expect(result.current.results.map((r) => r.title)).toEqual(["new"]);
  });

  it("clears the loading state when the query drops below min chars", () => {
    vi.spyOn(api, "autocomplete").mockResolvedValue({ results: [] } as never);
    const { result, rerender } = renderHook(({ q }) => useSearch(q), {
      initialProps: { q: "ab" },
    });
    expect(result.current.loading).toBe(true);
    rerender({ q: "a" });
    expect(result.current.loading).toBe(false);
  });
});
