export interface User {
  id: number;
  email: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  created_at: string;
  is_owner?: boolean;
}

export interface Genre {
  name: string;
}

export interface FanGenre {
  genre: string;
  votes: number;
}

export interface AnimeSummary {
  id: number;
  anilist_id: number | null;
  title: string;
  title_english: string | null;
  title_japanese: string | null;
  description: string | null;
  image_url: string | null;
  banner_url: string | null;
  episodes: number | null;
  season: string | null;
  year: number | null;
  format: string | null;
  status: string | null;
  api_score: number | null;
  community_score: number | null;
  rating_count: number | null;
  genres?: Genre[];
  official_genres?: Genre[];
  fan_genres?: FanGenre[];
}

export interface AnimeDetail extends AnimeSummary {
  studios?: string[];
  start_date?: string | null;
  end_date?: string | null;
  duration?: number | null;
  source?: string | null;
  user_rating?: { score: number; review: string | null } | null;
  user_genre_votes?: string[];
  user_watch_status?: { status: WatchStatus; episodes_watched: number; is_favorite: boolean } | null;
}

export type WatchStatus =
  | "watching"
  | "completed"
  | "plan_to_watch"
  | "on_hold"
  | "dropped";

export type ViewMode = "large" | "compact" | "list";
export type GenreMatchMode = "any" | "all";
export type WatchlistSort = "updated" | "created" | "title" | "score";

export interface WatchEntry {
  id: number;
  anime: AnimeSummary;
  status: WatchStatus;
  episodes_watched: number;
  is_favorite: boolean;
  updated_at: string;
  created_at: string;
  /** The score (1-10) this user gave the anime, or null if unrated. */
  score?: number | null;
  /** Fan-genre tags this user assigned to the anime. */
  genres?: string[];
}

export interface WatchStats {
  watching: number;
  completed: number;
  plan_to_watch: number;
  on_hold: number;
  dropped: number;
  favorites: number;
}

export interface Rating {
  id: number;
  anime: AnimeSummary;
  score: number;
  review: string | null;
  created_at: string;
}

export interface Recommendation {
  anime: AnimeSummary;
  reason: string;
  score: number;
}

export interface TasteProfile {
  top_genres: Array<{ genre: string; weight: number }>;
  avg_score: number | null;
  rating_count: number;
}

export interface ChatAnimeRef {
  id: number | null;
  title: string;
  image_url: string | null;
  year?: number | null;
  genres?: string[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatResponse {
  response: string;
  suggested_anime?: ChatAnimeRef[];
  suggested_actions?: string[];
  // The anime the user asked to match against ("something like X"),
  // rendered as its own card above the suggestions.
  seed_anime?: ChatAnimeRef | null;
}

export interface Collection {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  color: string;
  icon: string;
  is_public: boolean;
  share_token: string | null;
  items_count: number;
  created_at: string;
  updated_at: string;
}

export interface CollectionItem {
  id: number;
  anime: AnimeSummary;
  note: string | null;
  position: number;
  added_at: string;
}

export interface CollectionDetail extends Collection {
  items: CollectionItem[];
  owner?: { id: number; username: string; display_name: string | null };
}

export interface StatsOverview {
  total_rated: number;
  total_watched: number;
  hours_watched: number;
  favorite_count: number;
  avg_rating: number | null;
  top_genre: string | null;
  streak_days: number;
}

export interface StatsHeatmapCell {
  date: string;
  count: number;
}

export interface StatsHeatmap {
  cells: StatsHeatmapCell[];
  max: number;
}

export interface StatsGenreSlice {
  genre: string;
  count: number;
}

export interface StatsRatingBucket {
  score: number;
  count: number;
}

export interface StatsOverviewResponse {
  overview: StatsOverview;
  rating_distribution: StatsRatingBucket[];
  top_genres: StatsGenreSlice[];
}

export type Season = "winter" | "spring" | "summer" | "fall";

export interface SeasonalResponse {
  year: number;
  season: Season;
  anime: AnimeSummary[];
}

export type ActivityKind =
  | "rating"
  | "watch_status"
  | "favorite"
  | "collection_item"
  | "collection_create"
  | "genre_vote"
  | "dub_report";

export type DubReportStatus = "pending" | "accepted" | "rejected";

export interface DubReport {
  id: number;
  episode_id: number;
  submitted_by: number;
  air_date: string;
  status: DubReportStatus;
  note: string | null;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by: number | null;
}

export type WaitlistStatus = "pending" | "approved" | "registered";

export interface WaitlistEntry {
  id: number;
  email: string;
  created_at: string;
  status: WaitlistStatus;
  invite_code: string | null;
  approved_at: string | null;
  code_used_at: string | null;
}

export interface ActivityEvent {
  id: number;
  kind: ActivityKind;
  created_at: string;
  anime?: AnimeSummary;
  meta: Record<string, unknown>;
}

export interface ActivityResponse {
  events: ActivityEvent[];
  page: number;
  pages: number;
}

// Anime-vs-anime comparison (GET /api/compare?a=&b=). The backend payload
// includes the caller's own per-anime rating + fan-genre votes so the UI can
// show "your score" side-by-side without a second round-trip.

export interface AnimeCompareUserSide {
  score: number | null;
  review: string | null;
  fan_genres: string[];
}

export interface AnimeCompareSide {
  anime: AnimeSummary & {
    studio?: string | null;
  };
  user: AnimeCompareUserSide;
}

export interface AnimeCompareResponse {
  a: AnimeCompareSide;
  b: AnimeCompareSide;
  shared: {
    official_genres: string[];
    fan_genres: string[];
    studios: string[];
  };
  unique: {
    a_only_official_genres: string[];
    b_only_official_genres: string[];
  };
}

export interface Episode {
  id: number;
  episode_number: number;
  air_date_sub: string | null;
  air_date_dub: string | null;
  /** Raw dub provenance, e.g. "crunchyroll_rss" | "animeschedule" | "user:<name>" | "synthetic_lag_8w" | null. */
  dub_source?: string | null;
  /** True only when the dub date is the synthetic (sub + lag) projection. */
  dub_estimated?: boolean;
}

export interface AnimeEpisodesResponse {
  episodes: Episode[];
  next_sub: Episode | null;
  next_dub: Episode | null;
}

// /api/schedule/week response (revamp 2026-05-24)

export interface ScheduleWeekEpisode {
  id: number;
  anime_id: number;
  anime: AnimeSummary;
  episode_number: number;
  air_time_utc: string;
  type: "sub" | "dub";
  estimated: boolean;
  on_watchlist: boolean;
}

export interface ScheduleWeekDay {
  date: string;
  episodes: ScheduleWeekEpisode[];
}

export interface ScheduleWeekResponse {
  week_start: string;
  days: ScheduleWeekDay[];
}
