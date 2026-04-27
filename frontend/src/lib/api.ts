import type {
  AnimeDetailResponse,
  AnimeListResponse,
  AuthResponse,
  AutocompleteResponse,
  ChatRequest,
  FavoriteResponse,
  RatingsResponse,
  RecommendationsResponse,
  ReviewResponse,
  SimilarResponse,
  WatchStatsResponse,
  WatchStatusResponse,
  WatchlistResponse,
} from "@/types/api";
import type { ChatResponse } from "@/types/models";

const BASE =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1")
    ? "http://localhost:5000/api"
    : window.location.origin + "/api";

const TOKEN_KEY = "bingery_token";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) ?? {}),
  };
  const t = getToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;

  const res = await fetch(BASE + path, { ...init, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new ApiError(data.error ?? `Request failed (${res.status})`, res.status);
  }
  return data as T;
}

export const api = {
  getToken,
  setToken,
  base: BASE,

  health: () => request<{ ok: boolean }>("/health"),

  login: (body: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  register: (body: { email: string; password: string; username: string }) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  me: () => request<{ user: AuthResponse["user"] }>("/auth/me"),
  logout: () => {
    setToken(null);
  },

  getAnime: (q = "") => request<AnimeListResponse>("/anime" + q),
  getAnimeDetail: (id: number) => request<AnimeDetailResponse>(`/anime/${id}`),
  getSimilar: (id: number) => request<SimilarResponse>(`/anime/${id}/similar`),
  submitReview: (
    id: number,
    body: { score: number; review?: string; genres?: string[] }
  ) =>
    request<ReviewResponse>(`/anime/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  autocomplete: (q: string) =>
    request<AutocompleteResponse>(`/search/autocomplete?q=${encodeURIComponent(q)}`),

  getWatchlist: (q = "") => request<WatchlistResponse>("/watchlist" + q),
  getWatchlistStats: () => request<WatchStatsResponse>("/watchlist/stats"),
  setWatchStatus: (
    animeId: number,
    body: { status: string; episodes_watched?: number }
  ) =>
    request<WatchStatusResponse>(`/watchlist/anime/${animeId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  toggleFavorite: (animeId: number) =>
    request<FavoriteResponse>(`/watchlist/anime/${animeId}/favorite`, {
      method: "POST",
    }),
  removeFromWatchlist: (animeId: number) =>
    request<{ ok: boolean }>(`/watchlist/anime/${animeId}`, {
      method: "DELETE",
    }),

  getMyRatings: () => request<RatingsResponse>("/ratings/me"),

  getRecs: () => request<RecommendationsResponse>("/recommend"),

  chatMessage: (body: ChatRequest) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
