// Fan-genre tags shown in the rating panel.
//
// IMPORTANT: this list MUST stay in sync with ALLOWED_FAN_GENRES in
// routes/ratings.py — the backend rejects any vote whose tag isn't in its
// allowlist, so every option offered here has to exist there too.
export const FAN_GENRES = [
  // Standard
  "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror",
  "Mystery", "Romance", "Sci-Fi", "Slice of Life", "Supernatural",
  "Thriller", "Sports", "Music",
  // Demographic
  "Shounen", "Shoujo", "Seinen", "Josei", "Kodomomuke",
  // Thematic / sub-genre
  "Isekai", "Mecha", "Magical Girl", "Harem", "Reverse Harem",
  "Martial Arts", "Military", "Psychological", "Ecchi",
  "Gore", "Survival", "Post-Apocalyptic", "Cyberpunk",
  "Steampunk", "Historical", "Samurai", "Vampire",
  "Zombie", "Demons", "Dark Fantasy", "Mythology",
  "Reincarnation", "Time Travel", "Virtual Reality",
  "Game", "Cooking", "Medical", "Detective",
  // Tone / style
  "Wholesome", "Feel-Good", "Tearjerker", "Mind-Bending",
  "Slow Burn", "Fast-Paced", "Episodic", "Satirical",
  "Coming of Age", "Tragic",
  // Setting
  "School", "Workplace", "Space", "Underworld", "Urban",
  "Rural", "Kingdom", "Tournament", "Dungeon",
  // More broad tags (kept in sync with ALLOWED_FAN_GENRES in routes/ratings.py)
  "Iyashikei", "Idol", "Spy", "Crime", "Superpower", "Parody",
  "Dark Comedy", "Romantic Comedy", "Yuri", "Boys' Love",
  "Gender Bender", "Heist", "Battle Royale", "War", "Surreal",
  "Bittersweet", "Found Family", "Revenge", "Anti-Hero",
  "Ensemble Cast", "Nonlinear", "Noir", "Western", "Body Horror",
];

// Hand-picked colors for the most common genres. Anything not listed falls
// back to a stable, deterministic color derived from its name (below) so the
// full tag set stays visually varied instead of one flat default.
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
  Thriller: "#f97316",
  Shounen: "#3b82f6",
  Seinen: "#64748b",
  Isekai: "#10b981",
  Psychological: "#7c3aed",
  "Dark Fantasy": "#881337",
};

// Same name -> same hue, every time. Keeps the ~80 tags distinguishable
// without hand-defining a color for each one.
function hashHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

export function genreColor(name: string): string {
  const fixed = GENRE_COLORS[name];
  if (fixed) return fixed;
  return `hsl(${hashHue(name)} 62% 55%)`;
}
