import { create } from "zustand";
import { api, ApiError, onUnauthorized } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import type { User } from "@/types/models";

export type AuthStatus = "idle" | "loading" | "authenticated" | "error";

interface AuthState {
  user: User | null;
  status: AuthStatus;
  error: string | null;
  signIn: (body: { email: string; password: string }) => Promise<void>;
  /** Starts sign-up: sends the verification code. Does NOT authenticate. */
  signUp: (body: { email: string; password: string; username: string; display_name?: string }) => Promise<void>;
  /** Completes sign-up: exchanges email+code for a token and signs in. */
  verifyEmail: (body: { email: string; code: string }) => Promise<void>;
  resendCode: (body: { email: string }) => Promise<void>;
  signOut: () => void;
  restore: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  status: "idle",
  error: null,
  async signIn(body) {
    set({ status: "loading", error: null });
    try {
      const res = await api.login(body);
      api.setToken(res.token);
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  async signUp(body) {
    set({ status: "loading", error: null });
    try {
      await api.register(body);
      // No token yet — the verify step completes authentication.
      set({ status: "idle" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  async verifyEmail(body) {
    set({ status: "loading", error: null });
    try {
      const res = await api.verifyEmail(body);
      api.setToken(res.token);
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  async resendCode(body) {
    try {
      await api.resendCode(body);
      set({ error: null });
    } catch (e) {
      set({ error: (e as Error).message });
      throw e;
    }
  },
  signOut() {
    api.setToken(null);
    // User-scoped data must not survive into the next session.
    queryClient.clear();
    set({ user: null, status: "idle", error: null });
  },
  async restore() {
    if (!api.getToken()) return;
    set({ status: "loading" });
    try {
      const res = await api.me();
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      // Only discard the token when the server rejected it — a transient
      // network failure must not log the user out.
      if (e instanceof ApiError && (e.status === 401 || e.status === 422)) {
        api.setToken(null);
      }
      set({ user: null, status: "idle" });
    }
  },
}));

// Expired/revoked token detected mid-session by the API client: leave the
// authenticated state and drop user-scoped cache.
onUnauthorized(() => {
  queryClient.clear();
  useAuth.setState({ user: null, status: "idle" });
});
