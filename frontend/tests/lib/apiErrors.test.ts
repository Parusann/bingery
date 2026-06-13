import { describe, expect, it, afterEach, vi } from "vitest";
import { api, ApiError, onUnauthorized } from "@/lib/api";

describe("request error handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    onUnauthorized(null);
    localStorage.clear();
  });

  it("wraps non-JSON error bodies in ApiError instead of SyntaxError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        text: () => Promise.resolve("<html>Bad gateway</html>"),
      })
    );
    await expect(api.health()).rejects.toBeInstanceOf(ApiError);
    await expect(api.health()).rejects.toMatchObject({ status: 502 });
  });

  it("drops the token and notifies on 401 from a non-auth endpoint", async () => {
    api.setToken("stale-token");
    const handler = vi.fn();
    onUnauthorized(handler);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: () => Promise.resolve(JSON.stringify({ error: "expired" })),
      })
    );
    await expect(api.getWatchlist("")).rejects.toMatchObject({ status: 401 });
    expect(api.getToken()).toBeNull();
    expect(handler).toHaveBeenCalled();
  });

  it("does not fire the unauthorized handler for auth endpoints", async () => {
    api.setToken("stale-token");
    const handler = vi.fn();
    onUnauthorized(handler);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: () => Promise.resolve(JSON.stringify({ error: "bad creds" })),
      })
    );
    await expect(
      api.login({ email: "a@b.c", password: "x" })
    ).rejects.toMatchObject({ status: 401 });
    expect(handler).not.toHaveBeenCalled();
  });
});
