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
import { useNsfw } from "@/stores/nsfw";

// Endpoints whose anime payloads should respect the global NSFW toggle.
const NSFW_AWARE_PREFIXES = ["/anime", "/seasonal", "/recommend", "/schedule"];

function applyNsfwParam(path: string): string {
  if (!useNsfw.getState().visible) return path;
  if (!NSFW_AWARE_PREFIXES.some((p) => path.startsWith(p))) return path;
  if (/[?&]include_nsfw=/.test(path)) return path;
  return path + (path.includes("?") ? "&" : "?") + "include_nsfw=true";
}

// Honor VITE_API_URL when set — needed when the frontend is hosted on a
// different origin from the backend (e.g. Cloudflare Pages frontend + Fly.io
// backend). Set it to the backend origin without the /api suffix; we add
// /api here. Strips trailing slashes so both forms work.
//
// When unset, default to localhost:5000 in dev and same-origin /api in prod
// (the latter matches the Dockerfile setup where Flask serves the SPA).
const ENV_API_URL = (
  import.meta.env.VITE_API_URL as string | undefined
)?.replace(/\/+$/, "");

const BASE =
  ENV_API_URL && ENV_API_URL.length > 0
    ? ENV_API_URL.endsWith("/api")
      ? ENV_API_URL
      : `${ENV_API_URL}/api`
    : typeof window !== "undefined" &&
        (window.location.hostname === "localhost" ||
          window.location.hostname === "127.0.0.1")
      ? "http://localhost:5000/api"
      : window.location.origin + "/api";

const TOKEN_KEY = "bingery_token";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
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

  const res = await fetch(BASE + applyNsfwParam(path), { ...init, headers });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new ApiError(
      data.error ?? `Request failed (${res.status})`,
      res.status,
      typeof data.stop_reason === "string" ? data.stop_reason : undefined,
    );
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
  register: (body: { email: string; password: string; username: string; display_name?: string }) =>
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

  getRecs: () => request<RecommendationsResponse>("/recommend/for-me"),

  chatMessage: (body: ChatRequest) =>
    request<ChatResponse>("/chat/message", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getCollections: () =>
    request<import("@/types/api").CollectionsListResponse>("/collections"),
  getCollection: (id: number) =>
    request<import("@/types/api").CollectionResponse>(`/collections/${id}`),
  getSharedCollection: (token: string) =>
    request<import("@/types/api").CollectionResponse>(`/collections/public/${token}`),
  createCollection: (body: {
    name: string;
    description?: string;
    is_public?: boolean;
  }) =>
    request<import("@/types/api").CollectionMutation>("/collections", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateCollection: (
    id: number,
    body: { name?: string; description?: string; is_public?: boolean }
  ) =>
    request<import("@/types/api").CollectionMutation>(`/collections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteCollection: (id: number) =>
    request<{ ok: boolean }>(`/collections/${id}`, { method: "DELETE" }),
  addToCollection: (
    id: number,
    body: { anime_id: number; note?: string }
  ) =>
    request<{ item: import("@/types/models").CollectionItem }>(
      `/collections/${id}/items`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  removeFromCollection: (id: number, animeId: number) =>
    request<{ ok: boolean }>(`/collections/${id}/items/${animeId}`, {
      method: "DELETE",
    }),

  getStatsOverview: () =>
    request<import("@/types/api").StatsOverviewResp>("/stats/overview"),
  getStatsHeatmap: () =>
    request<import("@/types/api").StatsHeatmapResp>("/stats/heatmap"),

  getSeasonal: (year?: number, season?: import("@/types/models").Season) =>
    request<import("@/types/api").SeasonalResp>(
      `/seasonal${year && season ? `?year=${year}&season=${season}` : ""}`
    ),

  getActivity: (page = 1) =>
    request<import("@/types/api").ActivityResp>(`/activity?page=${page}`),

  // Anime-vs-anime comparison. The user-vs-user path is dropped because
  // there's only one demo user; this hits the richer /api/compare?a=&b=
  // endpoint which returns side-by-side anime payloads plus the caller's
  // own ratings.
  compareAnime: (aId: number, bId: number) =>
    request<import("@/types/api").CompareResp>(
      `/compare?a=${aId}&b=${bId}`
    ),

  getSchedule: (days = 7, kind: "sub" | "dub" | "both" = "sub") =>
    request<import("@/types/api").ScheduleResp>(
      `/schedule/upcoming?days=${days}&kind=${kind}`
    ),

  getScheduleWeek: (
    week: string,
    lang: "sub" | "dub" | "both" = "both",
    mine = false,
  ) => {
    const params = new URLSearchParams({
      week,
      lang,
      mine: mine ? "1" : "0",
    });
    return request<import("@/types/api").ScheduleWeekResp>(
      `/schedule/week?${params}`
    );
  },

  getAnimeEpisodes: (animeId: number) =>
    request<import("@/types/api").AnimeEpisodesResp>(`/anime/${animeId}/episodes`),

  createDubReport: (body: import("@/types/api").CreateDubReportRequest) =>
    request<import("@/types/api").DubReportResp>("/dub-reports", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listDubReports: (status?: import("@/types/models").DubReportStatus) =>
    request<import("@/types/api").DubReportListResp>(
      "/dub-reports" + (status ? `?status=${status}` : "")
    ),

  updateDubReport: (
    id: number,
    body: import("@/types/api").UpdateDubReportRequest
  ) =>
    request<import("@/types/api").DubReportResp>(`/dub-reports/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
};
