export interface User {
  id: number;
  email: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  created_at: string;
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

export interface WatchEntry {
  id: number;
  anime: AnimeSummary;
  status: WatchStatus;
  episodes_watched: number;
  is_favorite: boolean;
  updated_at: string;
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
}

export interface Collection {
  id: number;
  owner_id: number;
  title: string;
  description: string | null;
  is_public: boolean;
  share_token: string | null;
  item_count: number;
  cover_image_url: string | null;
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
  owner: { id: number; username: string; display_name: string | null };
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
  | "genre_vote";

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

export interface CompareTaste {
  shared_genres: StatsGenreSlice[];
  only_a_genres: StatsGenreSlice[];
  only_b_genres: StatsGenreSlice[];
  shared_anime: AnimeSummary[];
  score_agreement: number;
}

export interface CompareResponse {
  user_a: { id: number; username: string; display_name: string | null };
  user_b: { id: number; username: string; display_name: string | null };
  taste: CompareTaste;
}

export interface Episode {
  id: number;
  episode_number: number;
  air_date_sub: string | null;
  air_date_dub: string | null;
}

export interface ScheduleEpisode {
  id: number;
  episode_number: number;
  air_at: string;
  anime: AnimeSummary;
  kind: "sub" | "dub";
}

export interface ScheduleDay {
  date: string;
  episodes: ScheduleEpisode[];
}

export interface ScheduleResponse {
  days: ScheduleDay[];
}

export interface AnimeEpisodesResponse {
  episodes: Episode[];
  next_sub: Episode | null;
  next_dub: Episode | null;
}
