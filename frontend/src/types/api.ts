import type {
  AnimeDetail,
  AnimeSummary,
  ChatMessage,
  ChatResponse,
  FanGenre,
  Rating,
  Recommendation,
  TasteProfile,
  User,
  WatchEntry,
  WatchStats,
  WatchStatus,
} from "./models";

export interface AuthResponse {
  token: string;
  user: User;
}

export interface AnimeListResponse {
  anime: AnimeSummary[];
  page: number;
  pages: number;
  total: number;
}

export interface AnimeDetailResponse {
  anime: AnimeDetail;
}

export interface SimilarResponse {
  similar: AnimeSummary[];
}

export interface AutocompleteResponse {
  results: AnimeSummary[];
}

export interface ReviewResponse {
  community_score: number;
  rating_count: number;
  fan_genres: FanGenre[];
}

export interface WatchlistResponse {
  entries: WatchEntry[];
}

export interface WatchStatsResponse {
  stats: WatchStats;
}

export interface WatchStatusResponse {
  entry: WatchEntry;
}

export interface FavoriteResponse {
  is_favorite: boolean;
  entry: WatchEntry | null;
}

export interface RatingsResponse {
  ratings: Rating[];
}

export interface RecommendationsResponse {
  recommendations: Recommendation[];
  taste_profile: TasteProfile | null;
}

export interface ChatRequest {
  message: string;
  conversation: ChatMessage[];
  mode: "recommend" | "rate" | "onboard";
}

export type { WatchStatus, ChatResponse };
