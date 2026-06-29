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
  ScheduleWeekResponse,
} from "./models";

export interface AuthResponse {
  token: string;
  user: User;
}

export interface RegisterPendingResponse {
  verification_required: true;
  email: string;
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

export interface RelatedEntry {
  anilist_id: number;
  id: number | null;          // local Bingery id, or null if not in catalog
  title: string;
  format: string | null;      // "TV" | "Movie" | "OVA" | "Special" | ...
  release_date: string | null; // ISO date if fully known, else null
  year: number | null;
  image_url: string | null;
  is_current: boolean;
}

export interface RelatedResponse {
  related: RelatedEntry[];
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

import type { Collection, CollectionDetail } from "./models";

export interface CollectionsListResponse {
  collections: Collection[];
}

export interface CollectionResponse {
  collection: CollectionDetail;
}

export interface CollectionMutation {
  collection: Collection;
}

import type { StatsHeatmap, StatsOverviewResponse } from "./models";

export interface StatsOverviewResp extends StatsOverviewResponse {}
export interface StatsHeatmapResp {
  heatmap: StatsHeatmap;
}

import type { SeasonalResponse } from "./models";
export interface SeasonalResp extends SeasonalResponse {}

import type { ActivityResponse } from "./models";
export interface ActivityResp extends ActivityResponse {}

import type { AnimeCompareResponse } from "./models";
export interface CompareResp extends AnimeCompareResponse {}

import type { AnimeEpisodesResponse } from "./models";
export interface AnimeEpisodesResp extends AnimeEpisodesResponse {}

import type { DubReport } from "./models";
export interface DubReportListResp {
  reports: DubReport[];
}
export interface DubReportResp {
  report: DubReport;
}
export interface CreateDubReportRequest {
  episode_id: number;
  air_date: string;
  note?: string;
}
export interface UpdateDubReportRequest {
  status: "accepted" | "rejected";
}

export interface ScheduleWeekResp extends ScheduleWeekResponse {}
