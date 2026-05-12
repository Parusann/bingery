import { describe, expect, it, beforeEach, vi, afterEach } from "vitest";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

beforeEach(() => {
  localStorage.clear();
  useAuth.setState({ user: null, status: "idle" });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("auth store", () => {
  it("starts idle with no user", () => {
    expect(useAuth.getState().user).toBeNull();
    expect(useAuth.getState().status).toBe("idle");
  });

  it("signIn stores user + token", async () => {
    vi.spyOn(api, "login").mockResolvedValue({
      token: "xyz",
      user: {
        id: 1,
        email: "a@b.c",
        username: "me",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "2026-01-01",
      },
    });
    await useAuth.getState().signIn({ email: "a@b.c", password: "pw" });
    expect(useAuth.getState().user?.id).toBe(1);
    expect(api.getToken()).toBe("xyz");
    expect(useAuth.getState().status).toBe("authenticated");
  });

  it("signOut clears user + token", () => {
    api.setToken("abc");
    useAuth.setState({
      user: {
        id: 1,
        email: "a@b",
        username: "u",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "",
      },
      status: "authenticated",
    });
    useAuth.getState().signOut();
    expect(useAuth.getState().user).toBeNull();
    expect(api.getToken()).toBeNull();
  });

  it("restore() fetches /me when token present", async () => {
    api.setToken("xyz");
    vi.spyOn(api, "me").mockResolvedValue({
      user: {
        id: 2,
        email: "c@d",
        username: "them",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "",
      },
    });
    await useAuth.getState().restore();
    expect(useAuth.getState().user?.id).toBe(2);
  });
});
