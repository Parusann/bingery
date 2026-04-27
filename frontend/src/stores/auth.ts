import { create } from "zustand";
import { api } from "@/lib/api";
import type { User } from "@/types/models";

export type AuthStatus = "idle" | "loading" | "authenticated" | "error";

interface AuthState {
  user: User | null;
  status: AuthStatus;
  error: string | null;
  signIn: (body: { email: string; password: string }) => Promise<void>;
  signUp: (body: { email: string; password: string; username: string }) => Promise<void>;
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
      const res = await api.register(body);
      api.setToken(res.token);
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  signOut() {
    api.setToken(null);
    set({ user: null, status: "idle", error: null });
  },
  async restore() {
    if (!api.getToken()) return;
    set({ status: "loading" });
    try {
      const res = await api.me();
      set({ user: res.user, status: "authenticated" });
    } catch {
      api.setToken(null);
      set({ user: null, status: "idle" });
    }
  },
}));
