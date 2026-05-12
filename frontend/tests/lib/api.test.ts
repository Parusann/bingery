// @vitest-environment jsdom
import { describe, expect, it, beforeEach, vi, afterEach } from "vitest";
import { api, ApiError } from "@/lib/api";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends Authorization header when token present", async () => {
    api.setToken("abc123");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ ok: true }),
    });
    await api.health();
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["Authorization"]).toBe("Bearer abc123");
  });

  it("omits Authorization header when no token", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ ok: true }),
    });
    await api.health();
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["Authorization"]).toBeUndefined();
  });

  it("throws ApiError with server message on non-OK", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ error: "Not found" }),
    });
    await expect(api.getAnimeDetail(999)).rejects.toBeInstanceOf(ApiError);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ error: "Not found" }),
    });
    await expect(api.getAnimeDetail(999)).rejects.toMatchObject({
      message: "Not found",
      status: 404,
    });
  });

  it("login persists token via setToken caller", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () =>
        JSON.stringify({ token: "t0k", user: { id: 1, email: "a@b", username: "a", display_name: null, avatar_url: null, bio: null, created_at: "" } }),
    });
    const res = await api.login({ email: "a@b", password: "pw" });
    api.setToken(res.token);
    expect(api.getToken()).toBe("t0k");
  });
});
