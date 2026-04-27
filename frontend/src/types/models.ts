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
