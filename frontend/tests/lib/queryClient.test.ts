import { describe, expect, it, vi, afterEach } from "vitest";
import { queryClient } from "@/lib/queryClient";
import { ApiError } from "@/lib/api";
import { useNsfw } from "@/stores/nsfw";

describe("queryClient defaults", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useNsfw.setState({ visible: false });
  });

  it("does not retry 4xx ApiErrors but retries transient failures once", () => {
    const retry = queryClient.getDefaultOptions().queries?.retry;
    expect(typeof retry).toBe("function");
    const fn = retry as (count: number, error: unknown) => boolean;
    expect(fn(0, new ApiError("nope", 404))).toBe(false);
    expect(fn(0, new ApiError("auth", 401))).toBe(false);
    expect(fn(0, new TypeError("network down"))).toBe(true);
    expect(fn(1, new TypeError("network down"))).toBe(false);
    expect(fn(0, new ApiError("upstream", 502))).toBe(true);
  });

  it("invalidates all queries when the NSFW toggle flips", () => {
    const spy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue(undefined as never);
    useNsfw.getState().toggle();
    expect(spy).toHaveBeenCalled();
  });
});
