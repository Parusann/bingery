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
  "Slow Burn", "Fast-Paced", "Episodic", "Satirical", "Tragic",
  // Setting (common)
  "School", "Space",
  // More broad tags (kept in sync with ALLOWED_FAN_GENRES in routes/ratings.py)
  "Iyashikei", "Idol", "Spy", "Crime", "Superpower", "Parody",
  "Dark Comedy", "Romantic Comedy", "Yuri", "Boys' Love",
  "Gender Bender", "Heist", "Battle Royale", "War", "Surreal",
  "Bittersweet", "Noir", "Western", "Body Horror",
];

// Hand-picked colors for the most common genres — retuned to sit on the warm
// dark stage: dusty, film-grade hues at a consistent perceived lightness
// (~L66–74) instead of the old raw saturated palette. Anything not listed
// falls back to a stable, deterministic color derived from its name (below)
// at the same softened saturation, so the full tag set stays varied without
// ever screaming against the amber accent.
export const GENRE_COLORS: Record<string, string> = {
  Action: "#e07a6a",
  Adventure: "#e0a068",
  Comedy: "#9fc482",
  Drama: "#b89ac4",
  Fantasy: "#d98bb1",
  Horror: "#c47a7a",
  Mystery: "#8f9bc4",
  Romance: "#e88fa2",
  "Sci-Fi": "#7fb8c4",
  "Slice of Life": "#9BB8A8",
  Supernatural: "#ab8fd1",
  Thriller: "#d9985f",
  Shounen: "#7fa3d1",
  Seinen: "#9a94a8",
  Isekai: "#83c4a8",
  Psychological: "#9d86c9",
  "Dark Fantasy": "#c47a8f",
};

// Same name -> same hue, every time. Keeps the tags distinguishable
// without hand-defining a color for each one.
function hashHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

export function genreColor(name: string): string {
  const fixed = GENRE_COLORS[name];
  if (fixed) return fixed;
  return `hsl(${hashHue(name)} 34% 68%)`;
}
