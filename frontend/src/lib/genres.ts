export const GENRE_COLORS: Record<string, string> = {
  Action: "#ef4444",
  Adventure: "#f59e0b",
  Comedy: "#22c55e",
  Drama: "#8b5cf6",
  Fantasy: "#ec4899",
  Horror: "#991b1b",
  Mystery: "#6366f1",
  Romance: "#f43f5e",
  "Sci-Fi": "#06b6d4",
  "Slice of Life": "#84cc16",
  Supernatural: "#a855f7",
  Thriller: "#dc2626",
  Shounen: "#f97316",
  Seinen: "#14b8a6",
  Isekai: "#a78bfa",
};

export const GENRE_VOCAB = [
  "Action",
  "Adventure",
  "Comedy",
  "Drama",
  "Fantasy",
  "Horror",
  "Mystery",
  "Romance",
  "Sci-Fi",
  "Slice of Life",
  "Supernatural",
  "Thriller",
  "Shounen",
  "Seinen",
  "Isekai",
];

export function genreColor(name: string): string {
  return GENRE_COLORS[name] ?? "#6366f1";
}
