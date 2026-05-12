# Bingery Frontend Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a brand-new Vite + React 18 + TypeScript frontend in `frontend/` that reproduces every existing Bingery feature (discover, details, ratings, watchlist, for-you, chat, auth) on the new "restrained liquid glass" design system, and wire Flask to serve its production build.

**Architecture:** New frontend is a separate Vite app in `frontend/` with its own `package.json`, `tsconfig.json`, and `vitest.config.ts`. The legacy `static/index.html` stays untouched and functional until Plan 3's cut-over. A Vite dev-proxy forwards `/api/*` to Flask on port 5000. For production, `npm run build` emits to `frontend/dist/`; Flask's `static_folder` points to that directory. Design tokens are defined once in `src/design/tokens.ts`, consumed by Tailwind config and Framer Motion. LiquidGL (naughtyduk/liquidGL) powers ≤6 hero surfaces per page; cheaper CSS approximation handles bulk cards. TanStack Query owns server state (anime, watchlist, ratings, recs, chat); Zustand owns local auth state. React Router v6 replaces hash routing.

**Tech Stack:**
- Vite 5, React 18, TypeScript 5
- Tailwind CSS 3 + @fontsource for Fraunces/Inter/JetBrains Mono
- React Router 6
- TanStack Query 5 (server state) + Zustand 4 (auth)
- Framer Motion 11 (animation + page transitions)
- naughtyduk/liquidGL (vendored in `public/vendor/liquidgl.js`)
- Vitest + @testing-library/react (unit/component tests)
- Playwright 1 (e2e smoke)

---

## File Structure Map

```
frontend/
├── package.json                                # vite + react + deps
├── tsconfig.json                               # strict TS
├── tsconfig.node.json                          # for vite.config
├── vite.config.ts                              # proxy /api → localhost:5000
├── vitest.config.ts                            # jsdom env
├── tailwind.config.ts                          # tokens wired in
├── postcss.config.js                           # tailwind + autoprefixer
├── playwright.config.ts                        # e2e config
├── index.html                                  # Vite entry
├── .env.example                                # VITE_API_URL
├── .gitignore                                  # node_modules, dist
├── public/
│   ├── grain.svg                               # SVG noise overlay
│   └── vendor/
│       └── liquidgl.js                         # vendored naughtyduk lib
├── src/
│   ├── main.tsx                                # providers root
│   ├── App.tsx                                 # Router + AppShell
│   ├── index.css                               # Tailwind layers + base
│   ├── types/
│   │   ├── api.ts                              # API response types
│   │   └── models.ts                           # Anime, User, Rating, Entry
│   ├── lib/
│   │   ├── api.ts                              # typed fetch client
│   │   ├── queryClient.ts                      # TanStack Query + cache
│   │   ├── cn.ts                               # classnames util
│   │   └── genres.ts                           # genre color map
│   ├── stores/
│   │   └── auth.ts                             # Zustand auth store
│   ├── hooks/
│   │   ├── useAnimeList.ts                     # paginated discover
│   │   ├── useAnimeDetail.ts
│   │   ├── useSearch.ts                        # autocomplete
│   │   ├── useWatchlist.ts
│   │   ├── useRatings.ts
│   │   ├── useRecommendations.ts
│   │   └── useChat.ts
│   ├── design/
│   │   ├── tokens.ts                           # palette, spacing, motion
│   │   ├── motion.ts                           # Framer Motion presets
│   │   ├── Button.tsx                          # primary/ghost/glass variants
│   │   ├── Input.tsx
│   │   ├── Badge.tsx
│   │   ├── Skeleton.tsx
│   │   ├── Modal.tsx
│   │   ├── StarRating.tsx                      # 10-point w/ hover
│   │   ├── GlassCard.tsx                       # CSS approximation
│   │   ├── LiquidGLSurface.tsx                 # WebGL hero
│   │   ├── AmbientBlobs.tsx                    # 2 soft ambient blobs
│   │   └── GrainOverlay.tsx                    # 14% SVG noise
│   ├── layout/
│   │   ├── AppShell.tsx                        # outer frame
│   │   ├── Header.tsx                          # logo + user
│   │   └── NavBar.tsx                          # primary nav
│   ├── features/
│   │   ├── landing/LandingPage.tsx
│   │   ├── auth/
│   │   │   ├── AuthPage.tsx
│   │   │   └── AuthForm.tsx
│   │   ├── discover/
│   │   │   ├── DiscoverPage.tsx
│   │   │   ├── AnimeGrid.tsx
│   │   │   ├── AnimeCard.tsx
│   │   │   ├── SearchAutocomplete.tsx
│   │   │   └── FilterBar.tsx
│   │   ├── details/
│   │   │   ├── AnimeDetailPage.tsx
│   │   │   ├── DetailHero.tsx
│   │   │   ├── RatingPanel.tsx
│   │   │   ├── FanGenreBars.tsx
│   │   │   └── SimilarStrip.tsx
│   │   ├── watchlist/
│   │   │   ├── WatchlistPage.tsx
│   │   │   ├── StatusTabs.tsx
│   │   │   └── WatchStatusSelector.tsx
│   │   ├── for-you/
│   │   │   ├── ForYouPage.tsx
│   │   │   └── TasteProfile.tsx
│   │   └── chat/
│   │       ├── ChatPage.tsx
│   │       └── ChatAnimeCard.tsx
│   └── routes.tsx                              # route table
├── tests/
│   ├── lib/api.test.ts
│   ├── stores/auth.test.ts
│   ├── design/Button.test.tsx
│   ├── design/StarRating.test.tsx
│   └── features/AnimeCard.test.tsx
└── e2e/
    └── smoke.spec.ts

app.py                                          # static_folder switch (Task 20)
.gitignore                                      # frontend/node_modules, frontend/dist
```

---

## Task 1: Scaffold the Vite + React + TS workspace

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/.gitignore`
- Modify: `.gitignore` (append)

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "bingery-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:run": "vitest run",
    "e2e": "playwright test",
    "lint": "tsc -b --pretty"
  },
  "dependencies": {
    "@fontsource/fraunces": "^5.2.5",
    "@fontsource/inter": "^5.2.5",
    "@fontsource/jetbrains-mono": "^5.2.5",
    "@tanstack/react-query": "^5.56.2",
    "framer-motion": "^11.11.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0",
    "zustand": "^4.5.5"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.1",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.6.3",
    "vite": "^5.4.8",
    "vitest": "^2.1.2"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": false,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] },
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts", "vitest.config.ts", "tailwind.config.ts", "playwright.config.ts"]
}
```

- [ ] **Step 4: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:5000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#080510" />
    <title>Bingery — Anime Discovery</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 7: Create `frontend/src/App.tsx` (placeholder for now)**

```tsx
export default function App() {
  return <div className="p-10 text-white">Bingery frontend scaffold online.</div>;
}
```

- [ ] **Step 8: Create `frontend/.gitignore`**

```
node_modules/
dist/
.env
.env.local
playwright-report/
test-results/
```

- [ ] **Step 9: Append frontend paths to root `.gitignore`**

Open `C:\Users\parus\Downloads\bingery-update\.gitignore` and append these lines at the end (keep the trailing blank line):

```
frontend/node_modules/
frontend/dist/
frontend/.env
frontend/test-results/
frontend/playwright-report/
```

- [ ] **Step 10: Install deps and verify dev server boots**

Run from `frontend/`:

```bash
cd frontend
npm install
npm run dev -- --port 5173 --host 127.0.0.1 &
sleep 3
curl -s http://127.0.0.1:5173/ | grep -q "<div id=\"root\">" && echo "OK"
kill %1 2>/dev/null || true
```

Expected: `OK` printed.

- [ ] **Step 11: Verify `tsc -b` type-checks clean**

```bash
cd frontend && npx tsc -b --pretty
```

Expected: no output (success).

- [ ] **Step 12: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts frontend/index.html frontend/src/main.tsx frontend/src/App.tsx frontend/.gitignore .gitignore
git commit -m "Scaffold Vite React TypeScript frontend workspace"
```

---

## Task 2: Design tokens, Tailwind config, base CSS

**Files:**
- Create: `frontend/src/design/tokens.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/index.css`
- Create: `frontend/public/grain.svg`

- [ ] **Step 1: Create `frontend/src/design/tokens.ts`**

```ts
export const palette = {
  bg: "#080510",
  bgElevated: "#0f0a1a",
  surface: "rgba(255,255,255,0.04)",
  surfaceStrong: "rgba(255,255,255,0.08)",
  border: "rgba(255,255,255,0.08)",
  borderStrong: "rgba(255,255,255,0.16)",
  amber: "#e6a680",
  amberSoft: "#d9b899",
  violet: "#b89ac4",
  violetSoft: "#9e86a9",
  text: "rgba(255,255,255,0.92)",
  textMuted: "rgba(255,255,255,0.64)",
  textDim: "rgba(255,255,255,0.42)",
  danger: "#e78a8a",
  success: "#8fc9a4",
} as const;

export const radius = {
  sm: "6px",
  md: "10px",
  lg: "16px",
  xl: "22px",
  pill: "9999px",
} as const;

export const space = {
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "18px",
  xl: "28px",
  xxl: "48px",
} as const;

export const font = {
  display: "'Fraunces', ui-serif, Georgia, serif",
  body: "'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace",
} as const;

export const motion = {
  ease: [0.22, 1, 0.36, 1] as const,
  easeOut: [0.16, 1, 0.3, 1] as const,
  duration: {
    fast: 0.18,
    base: 0.28,
    slow: 0.45,
    glacial: 0.7,
  },
  spring: {
    soft: { type: "spring" as const, stiffness: 260, damping: 28 },
    snappy: { type: "spring" as const, stiffness: 420, damping: 32 },
  },
} as const;

export const blur = {
  sm: "8px",
  md: "16px",
  lg: "28px",
  xl: "44px",
} as const;
```

- [ ] **Step 2: Create `frontend/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";
import { palette, radius, font } from "./src/design/tokens";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: palette.bg,
        "bg-elevated": palette.bgElevated,
        surface: palette.surface,
        "surface-strong": palette.surfaceStrong,
        border: palette.border,
        "border-strong": palette.borderStrong,
        amber: palette.amber,
        "amber-soft": palette.amberSoft,
        violet: palette.violet,
        "violet-soft": palette.violetSoft,
        text: palette.text,
        "text-muted": palette.textMuted,
        "text-dim": palette.textDim,
        danger: palette.danger,
        success: palette.success,
      },
      borderRadius: {
        sm: radius.sm,
        md: radius.md,
        lg: radius.lg,
        xl: radius.xl,
        pill: radius.pill,
      },
      fontFamily: {
        display: [font.display],
        sans: [font.body],
        mono: [font.mono],
      },
      backgroundImage: {
        grain: "url('/grain.svg')",
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 3: Create `frontend/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 4: Create `frontend/public/grain.svg`**

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <filter id="n">
    <feTurbulence type="fractalNoise" baseFrequency="0.92" numOctaves="2" stitchTiles="stitch"/>
    <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.14 0"/>
  </filter>
  <rect width="100%" height="100%" filter="url(#n)"/>
</svg>
```

- [ ] **Step 5: Create `frontend/src/index.css`**

```css
@import "@fontsource/fraunces/400.css";
@import "@fontsource/fraunces/600.css";
@import "@fontsource/inter/400.css";
@import "@fontsource/inter/500.css";
@import "@fontsource/inter/600.css";
@import "@fontsource/jetbrains-mono/400.css";

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    color-scheme: dark;
  }
  html, body, #root {
    height: 100%;
  }
  body {
    margin: 0;
    background: theme(colors.bg);
    color: theme(colors.text);
    font-family: theme(fontFamily.sans);
    font-size: 15px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    overflow-x: hidden;
  }
  h1, h2, h3 {
    font-family: theme(fontFamily.display);
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  button {
    font-family: inherit;
    color: inherit;
  }
  ::selection {
    background: rgba(230, 166, 128, 0.35);
    color: white;
  }
}

@layer utilities {
  .glass-edge {
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.08),
      inset 0 -1px 0 rgba(0, 0, 0, 0.18),
      0 24px 48px -24px rgba(0, 0, 0, 0.5);
  }
  .ring-amber {
    box-shadow: 0 0 0 1px rgba(230, 166, 128, 0.35);
  }
}
```

- [ ] **Step 6: Replace `frontend/src/App.tsx` to preview tokens**

```tsx
export default function App() {
  return (
    <div className="min-h-screen bg-bg text-text p-10 font-sans">
      <h1 className="text-5xl font-display text-amber mb-3">Bingery</h1>
      <p className="text-text-muted">Design tokens wired. Fraunces + Inter loaded.</p>
      <p className="font-mono text-violet text-sm mt-3">palette + tailwind + fonts online</p>
    </div>
  );
}
```

- [ ] **Step 7: Run dev server, visually verify styles render**

```bash
cd frontend && npm run dev -- --port 5173 &
sleep 3
curl -s http://127.0.0.1:5173/src/index.css | grep -q "tailwind" && echo "CSS served"
kill %1 2>/dev/null || true
```

Expected: `CSS served`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/design/tokens.ts frontend/tailwind.config.ts frontend/postcss.config.js frontend/src/index.css frontend/src/App.tsx frontend/public/grain.svg
git commit -m "Add design tokens, Tailwind config, base CSS, grain overlay"
```

---

## Task 3: API domain types + typed fetch client

**Files:**
- Create: `frontend/src/types/models.ts`
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tests/lib/api.test.ts`

- [ ] **Step 1: Create `frontend/src/types/models.ts`**

```ts
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
```

- [ ] **Step 2: Create `frontend/src/types/api.ts`**

```ts
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

export { WatchStatus, ChatResponse };
```

- [ ] **Step 3: Create `frontend/src/lib/api.ts`**

```ts
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
```

- [ ] **Step 4: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    css: false,
  },
});
```

- [ ] **Step 5: Create `frontend/tests/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 6: Write the failing test — `frontend/tests/lib/api.test.ts`**

```ts
import { describe, expect, it, beforeEach, vi, afterEach } from "vitest";
import { api, ApiError } from "@/lib/api";

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockReset();
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends Authorization header when token present", async () => {
    api.setToken("abc123");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ ok: true }),
    });
    await api.health();
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["Authorization"]).toBe("Bearer abc123");
  });

  it("omits Authorization header when no token", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () => JSON.stringify({ ok: true }),
    });
    await api.health();
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers["Authorization"]).toBeUndefined();
  });

  it("throws ApiError with server message on non-OK", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: async () => JSON.stringify({ error: "Not found" }),
    });
    await expect(api.getAnimeDetail(999)).rejects.toMatchObject({
      message: "Not found",
      status: 404,
    });
  });

  it("login persists token via setToken caller", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      text: async () =>
        JSON.stringify({ token: "t0k", user: { id: 1, email: "a@b", username: "a", display_name: null, avatar_url: null, bio: null, created_at: "" } }),
    });
    const res = await api.login({ email: "a@b", password: "pw" });
    api.setToken(res.token);
    expect(api.getToken()).toBe("t0k");
  });
});
```

- [ ] **Step 7: Run tests — expect fail (no impl yet if order swapped, else pass)**

```bash
cd frontend && npx vitest run tests/lib/api.test.ts
```

Expected: all 4 pass (client already exists from Step 3 — tests validate it).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/types/models.ts frontend/src/types/api.ts frontend/src/lib/api.ts frontend/vitest.config.ts frontend/tests/setup.ts frontend/tests/lib/api.test.ts
git commit -m "Add typed API client, domain types, and Vitest setup"
```

---

## Task 4: Zustand auth store + TanStack Query client

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/lib/queryClient.ts`
- Create: `frontend/src/lib/cn.ts`
- Create: `frontend/src/lib/genres.ts`
- Create: `frontend/tests/stores/auth.test.ts`

- [ ] **Step 1: Create `frontend/src/lib/cn.ts`**

```ts
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
```

- [ ] **Step 2: Create `frontend/src/lib/genres.ts`**

```ts
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

export const FAN_GENRES = [
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
```

- [ ] **Step 3: Write the failing test — `frontend/tests/stores/auth.test.ts`**

```ts
import { describe, expect, it, beforeEach, vi, afterEach } from "vitest";
import { useAuth } from "@/stores/auth";
import { api } from "@/lib/api";

beforeEach(() => {
  localStorage.clear();
  useAuth.setState({ user: null, status: "idle" });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("auth store", () => {
  it("starts idle with no user", () => {
    expect(useAuth.getState().user).toBeNull();
    expect(useAuth.getState().status).toBe("idle");
  });

  it("signIn stores user + token", async () => {
    vi.spyOn(api, "login").mockResolvedValue({
      token: "xyz",
      user: {
        id: 1,
        email: "a@b.c",
        username: "me",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "2026-01-01",
      },
    });
    await useAuth.getState().signIn({ email: "a@b.c", password: "pw" });
    expect(useAuth.getState().user?.id).toBe(1);
    expect(api.getToken()).toBe("xyz");
    expect(useAuth.getState().status).toBe("authenticated");
  });

  it("signOut clears user + token", () => {
    api.setToken("abc");
    useAuth.setState({
      user: {
        id: 1,
        email: "a@b",
        username: "u",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "",
      },
      status: "authenticated",
    });
    useAuth.getState().signOut();
    expect(useAuth.getState().user).toBeNull();
    expect(api.getToken()).toBeNull();
  });

  it("restore() fetches /me when token present", async () => {
    api.setToken("xyz");
    vi.spyOn(api, "me").mockResolvedValue({
      user: {
        id: 2,
        email: "c@d",
        username: "them",
        display_name: null,
        avatar_url: null,
        bio: null,
        created_at: "",
      },
    });
    await useAuth.getState().restore();
    expect(useAuth.getState().user?.id).toBe(2);
  });
});
```

- [ ] **Step 4: Run test — expect fail**

```bash
cd frontend && npx vitest run tests/stores/auth.test.ts
```

Expected: FAIL — `@/stores/auth` missing.

- [ ] **Step 5: Create `frontend/src/stores/auth.ts`**

```ts
import { create } from "zustand";
import { api } from "@/lib/api";
import type { User } from "@/types/models";

export type AuthStatus = "idle" | "loading" | "authenticated" | "error";

interface AuthState {
  user: User | null;
  status: AuthStatus;
  error: string | null;
  signIn: (body: { email: string; password: string }) => Promise<void>;
  signUp: (body: { email: string; password: string; username: string }) => Promise<void>;
  signOut: () => void;
  restore: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  status: "idle",
  error: null,
  async signIn(body) {
    set({ status: "loading", error: null });
    try {
      const res = await api.login(body);
      api.setToken(res.token);
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  async signUp(body) {
    set({ status: "loading", error: null });
    try {
      const res = await api.register(body);
      api.setToken(res.token);
      set({ user: res.user, status: "authenticated" });
    } catch (e) {
      set({ status: "error", error: (e as Error).message });
      throw e;
    }
  },
  signOut() {
    api.setToken(null);
    set({ user: null, status: "idle", error: null });
  },
  async restore() {
    if (!api.getToken()) return;
    set({ status: "loading" });
    try {
      const res = await api.me();
      set({ user: res.user, status: "authenticated" });
    } catch {
      api.setToken(null);
      set({ user: null, status: "idle" });
    }
  },
}));
```

- [ ] **Step 6: Run test — expect pass**

```bash
cd frontend && npx vitest run tests/stores/auth.test.ts
```

Expected: PASS — 4 tests.

- [ ] **Step 7: Create `frontend/src/lib/queryClient.ts`**

```ts
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/cn.ts frontend/src/lib/genres.ts frontend/src/stores/auth.ts frontend/src/lib/queryClient.ts frontend/tests/stores/auth.test.ts
git commit -m "Add auth store, TanStack Query client, genre palette, classnames util"
```

---

## Task 5: Router skeleton + provider wiring

**Files:**
- Create: `frontend/src/routes.tsx`
- Modify: `frontend/src/App.tsx` (replace placeholder)
- Modify: `frontend/src/main.tsx` (add providers)

- [ ] **Step 1: Create `frontend/src/routes.tsx`**

```tsx
import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";

const Placeholder = ({ name }: { name: string }) => (
  <div className="p-10 font-display text-3xl text-amber">{name}</div>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Placeholder name="Landing" /> },
      { path: "discover", element: <Placeholder name="Discover" /> },
      { path: "anime/:id", element: <Placeholder name="Anime detail" /> },
      { path: "watchlist", element: <Placeholder name="Watchlist" /> },
      { path: "for-you", element: <Placeholder name="For you" /> },
      { path: "chat", element: <Placeholder name="Chat" /> },
      { path: "auth", element: <Placeholder name="Auth" /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
```

- [ ] **Step 2: Create placeholder `frontend/src/layout/AppShell.tsx`**

```tsx
import { Outlet, Link } from "react-router-dom";

export default function AppShell() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="px-6 py-4 border-b border-border flex gap-4 items-center">
        <Link to="/" className="font-display text-xl text-amber">Bingery</Link>
        <nav className="flex gap-4 text-sm text-text-muted">
          <Link to="/discover">Discover</Link>
          <Link to="/watchlist">Watchlist</Link>
          <Link to="/for-you">For you</Link>
          <Link to="/chat">Chat</Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Replace `frontend/src/App.tsx`**

```tsx
import { RouterProvider } from "react-router-dom";
import { router } from "./routes";

export default function App() {
  return <RouterProvider router={router} />;
}
```

- [ ] **Step 4: Update `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { queryClient } from "./lib/queryClient";
import { useAuth } from "./stores/auth";
import "./index.css";

useAuth.getState().restore();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 5: Verify dev server renders and navigation works**

```bash
cd frontend && npm run dev -- --port 5173 &
sleep 3
curl -s http://127.0.0.1:5173/ | grep -q "root" && echo "OK home"
curl -s http://127.0.0.1:5173/discover | grep -q "root" && echo "OK discover"
kill %1 2>/dev/null || true
```

Expected: `OK home` and `OK discover`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes.tsx frontend/src/layout/AppShell.tsx frontend/src/App.tsx frontend/src/main.tsx
git commit -m "Wire router skeleton with provider chain and placeholder routes"
```

---

## Task 6: Motion presets + Button primitive

**Files:**
- Create: `frontend/src/design/motion.ts`
- Create: `frontend/src/design/Button.tsx`
- Create: `frontend/tests/design/Button.test.tsx`

- [ ] **Step 1: Create `frontend/src/design/motion.ts`**

```ts
import type { Transition, Variants } from "framer-motion";
import { motion as t } from "./tokens";

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1 },
};

export const pressDown: Variants = {
  rest: { scale: 1 },
  hover: { scale: 1.02 },
  press: { scale: 0.97 },
};

export const transitions: Record<string, Transition> = {
  ease: { duration: t.duration.base, ease: [...t.ease] },
  easeFast: { duration: t.duration.fast, ease: [...t.easeOut] },
  easeSlow: { duration: t.duration.slow, ease: [...t.ease] },
  spring: { ...t.spring.soft },
  springSnappy: { ...t.spring.snappy },
};

export const staggerChildren = (delay = 0.04): Transition => ({
  staggerChildren: delay,
});
```

- [ ] **Step 2: Write the failing test — `frontend/tests/design/Button.test.tsx`**

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "@/design/Button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Tap me</Button>);
    expect(screen.getByRole("button", { name: "Tap me" })).toBeInTheDocument();
  });

  it("fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables when loading", () => {
    render(<Button loading>Send</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("applies variant class", () => {
    const { rerender } = render(<Button variant="primary">P</Button>);
    expect(screen.getByRole("button").className).toMatch(/amber/);
    rerender(<Button variant="ghost">G</Button>);
    expect(screen.getByRole("button").className).toMatch(/ghost|transparent|border/);
  });
});
```

- [ ] **Step 3: Run test — expect fail**

```bash
cd frontend && npx vitest run tests/design/Button.test.tsx
```

Expected: FAIL — `@/design/Button` missing.

- [ ] **Step 4: Create `frontend/src/design/Button.tsx`**

```tsx
import { motion } from "framer-motion";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { transitions } from "./motion";

type Variant = "primary" | "ghost" | "glass" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
  children: ReactNode;
}

const variantClass: Record<Variant, string> = {
  primary:
    "bg-amber text-bg hover:bg-amber-soft focus-visible:ring-2 focus-visible:ring-amber/60",
  ghost:
    "bg-transparent text-text border border-border hover:border-border-strong hover:bg-white/[0.04]",
  glass:
    "bg-surface text-text border border-border backdrop-blur-md hover:bg-surface-strong glass-edge",
  danger:
    "bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25",
};

const sizeClass: Record<Size, string> = {
  sm: "h-8 px-3 text-xs rounded-md",
  md: "h-10 px-4 text-sm rounded-lg",
  lg: "h-12 px-6 text-base rounded-xl",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "primary", size = "md", loading, disabled, leading, trailing, className, children, ...rest },
  ref
) {
  const isDisabled = disabled || loading;
  return (
    <motion.button
      ref={ref}
      whileHover={isDisabled ? undefined : { scale: 1.02 }}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      transition={transitions.springSnappy}
      disabled={isDisabled}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium select-none",
        "transition-colors outline-none focus-visible:outline-none",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantClass[variant],
        sizeClass[size],
        className
      )}
      {...(rest as object)}
    >
      {loading ? (
        <span className="inline-block h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
      ) : (
        leading
      )}
      <span>{children}</span>
      {!loading && trailing}
    </motion.button>
  );
});
```

- [ ] **Step 5: Run test — expect pass**

```bash
cd frontend && npx vitest run tests/design/Button.test.tsx
```

Expected: PASS — 4 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/design/motion.ts frontend/src/design/Button.tsx frontend/tests/design/Button.test.tsx
git commit -m "Add Framer Motion presets and Button primitive with variants"
```

---

## Task 7: Input, Badge, Skeleton, Modal primitives

**Files:**
- Create: `frontend/src/design/Input.tsx`
- Create: `frontend/src/design/Badge.tsx`
- Create: `frontend/src/design/Skeleton.tsx`
- Create: `frontend/src/design/Modal.tsx`

- [ ] **Step 1: Create `frontend/src/design/Input.tsx`**

```tsx
import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  leading?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, error, leading, className, id, ...rest },
  ref
) {
  const domId = id ?? rest.name ?? undefined;
  return (
    <label htmlFor={domId} className="flex flex-col gap-1.5 text-sm">
      {label ? <span className="text-text-muted">{label}</span> : null}
      <div
        className={cn(
          "flex items-center gap-2 h-10 px-3 rounded-lg",
          "bg-surface border border-border focus-within:border-border-strong",
          "focus-within:ring-1 focus-within:ring-amber/40",
          error && "border-danger/60 focus-within:ring-danger/40"
        )}
      >
        {leading}
        <input
          ref={ref}
          id={domId}
          className={cn(
            "flex-1 bg-transparent outline-none placeholder:text-text-dim",
            className
          )}
          {...rest}
        />
      </div>
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </label>
  );
});
```

- [ ] **Step 2: Create `frontend/src/design/Badge.tsx`**

```tsx
import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface Props {
  color?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function Badge({ color = "#6366f1", children, className, style }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded",
        "border backdrop-blur-sm",
        className
      )}
      style={{
        background: color + "18",
        color,
        borderColor: color + "30",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 3: Create `frontend/src/design/Skeleton.tsx`**

```tsx
import { cn } from "@/lib/cn";

export function Skeleton({
  className,
  rounded = "md",
}: {
  className?: string;
  rounded?: "sm" | "md" | "lg" | "full";
}) {
  const r = {
    sm: "rounded-sm",
    md: "rounded-md",
    lg: "rounded-lg",
    full: "rounded-full",
  }[rounded];
  return (
    <div
      className={cn(
        "relative overflow-hidden bg-white/[0.04]",
        r,
        className
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.05] to-transparent animate-[shimmer_1.6s_infinite]" />
      <style>{`@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}`}</style>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/design/Modal.tsx`**

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { transitions } from "./motion";

interface Props {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  maxWidth?: string;
  className?: string;
}

export function Modal({ open, onClose, children, maxWidth = "640px", className }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={transitions.easeFast}
        >
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            className={cn(
              "relative z-10 w-full bg-bg-elevated border border-border rounded-xl glass-edge",
              "max-h-[92vh] overflow-y-auto",
              className
            )}
            style={{ maxWidth }}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={transitions.spring}
            role="dialog"
            aria-modal="true"
          >
            {children}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/design/Input.tsx frontend/src/design/Badge.tsx frontend/src/design/Skeleton.tsx frontend/src/design/Modal.tsx
git commit -m "Add Input, Badge, Skeleton, Modal primitives"
```

---

## Task 8: StarRating + GlassCard + AmbientBlobs + GrainOverlay

**Files:**
- Create: `frontend/src/design/StarRating.tsx`
- Create: `frontend/src/design/GlassCard.tsx`
- Create: `frontend/src/design/AmbientBlobs.tsx`
- Create: `frontend/src/design/GrainOverlay.tsx`
- Create: `frontend/tests/design/StarRating.test.tsx`

- [ ] **Step 1: Write the failing test — `frontend/tests/design/StarRating.test.tsx`**

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StarRating } from "@/design/StarRating";

describe("StarRating", () => {
  it("renders 10 slots", () => {
    render(<StarRating value={0} onChange={() => {}} />);
    expect(screen.getAllByRole("button")).toHaveLength(10);
  });

  it("shows current value", () => {
    render(<StarRating value={7} onChange={() => {}} />);
    expect(screen.getByLabelText("Rating 7 of 10")).toBeInTheDocument();
  });

  it("fires onChange on click", async () => {
    const onChange = vi.fn();
    render(<StarRating value={0} onChange={onChange} />);
    await userEvent.click(screen.getAllByRole("button")[4]);
    expect(onChange).toHaveBeenCalledWith(5);
  });

  it("ignores clicks in readOnly mode", async () => {
    const onChange = vi.fn();
    render(<StarRating value={3} onChange={onChange} readOnly />);
    await userEvent.click(screen.getAllByRole("button")[0]);
    expect(onChange).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test — expect fail**

```bash
cd frontend && npx vitest run tests/design/StarRating.test.tsx
```

Expected: FAIL — component missing.

- [ ] **Step 3: Create `frontend/src/design/StarRating.tsx`**

```tsx
import { useState } from "react";
import { cn } from "@/lib/cn";

interface Props {
  value: number;
  onChange: (v: number) => void;
  readOnly?: boolean;
  size?: number;
  className?: string;
}

export function StarRating({ value, onChange, readOnly, size = 20, className }: Props) {
  const [hover, setHover] = useState(0);
  const display = hover || value;
  return (
    <div
      className={cn("inline-flex items-center gap-0.5", className)}
      aria-label={`Rating ${value} of 10`}
      onMouseLeave={() => setHover(0)}
    >
      {Array.from({ length: 10 }).map((_, i) => {
        const n = i + 1;
        const on = n <= display;
        return (
          <button
            key={n}
            type="button"
            disabled={readOnly}
            onMouseEnter={() => !readOnly && setHover(n)}
            onClick={() => !readOnly && onChange(n)}
            className={cn(
              "p-0.5 transition-transform",
              !readOnly && "hover:scale-110 cursor-pointer",
              readOnly && "cursor-default"
            )}
            aria-label={`Rate ${n} of 10`}
          >
            <svg
              width={size}
              height={size}
              viewBox="0 0 24 24"
              fill={on ? "#e6a680" : "none"}
              stroke={on ? "#e6a680" : "rgba(255,255,255,0.3)"}
              strokeWidth="2"
              strokeLinejoin="round"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </button>
        );
      })}
      <span className="ml-2 text-sm text-text-muted tabular-nums">
        {display}/10
      </span>
    </div>
  );
}
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd frontend && npx vitest run tests/design/StarRating.test.tsx
```

Expected: PASS — 4 tests.

- [ ] **Step 5: Create `frontend/src/design/GlassCard.tsx`**

```tsx
import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface Props extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  tone?: "default" | "warm" | "cool";
  elevated?: boolean;
}

const toneClass: Record<NonNullable<Props["tone"]>, string> = {
  default: "bg-surface",
  warm: "bg-gradient-to-br from-amber/[0.08] to-transparent",
  cool: "bg-gradient-to-br from-violet/[0.08] to-transparent",
};

export function GlassCard({
  children,
  tone = "default",
  elevated,
  className,
  ...rest
}: Props) {
  return (
    <div
      {...rest}
      className={cn(
        "relative rounded-xl border border-border glass-edge",
        "backdrop-blur-md",
        toneClass[tone],
        elevated && "shadow-[0_24px_60px_-30px_rgba(0,0,0,0.6)]",
        className
      )}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend/src/design/AmbientBlobs.tsx`**

```tsx
import { motion } from "framer-motion";

export function AmbientBlobs() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 overflow-hidden z-0"
    >
      <motion.div
        className="absolute rounded-full blur-[160px]"
        style={{
          width: 720,
          height: 720,
          left: "-20%",
          top: "-30%",
          background:
            "radial-gradient(closest-side, rgba(230,166,128,0.45), rgba(230,166,128,0) 70%)",
        }}
        animate={{ x: [0, 40, 0], y: [0, 20, 0] }}
        transition={{ duration: 18, ease: "easeInOut", repeat: Infinity }}
      />
      <motion.div
        className="absolute rounded-full blur-[160px]"
        style={{
          width: 640,
          height: 640,
          right: "-15%",
          bottom: "-25%",
          background:
            "radial-gradient(closest-side, rgba(184,154,196,0.30), rgba(184,154,196,0) 70%)",
        }}
        animate={{ x: [0, -30, 0], y: [0, -15, 0] }}
        transition={{ duration: 22, ease: "easeInOut", repeat: Infinity }}
      />
    </div>
  );
}
```

- [ ] **Step 7: Create `frontend/src/design/GrainOverlay.tsx`**

```tsx
export function GrainOverlay() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 bg-grain opacity-[0.14] mix-blend-overlay"
    />
  );
}
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/design/StarRating.tsx frontend/src/design/GlassCard.tsx frontend/src/design/AmbientBlobs.tsx frontend/src/design/GrainOverlay.tsx frontend/tests/design/StarRating.test.tsx
git commit -m "Add StarRating, GlassCard, AmbientBlobs, GrainOverlay primitives"
```

---

## Task 9: LiquidGL surface wrapper

**Files:**
- Create: `frontend/public/vendor/liquidgl.js`
- Create: `frontend/src/design/LiquidGLSurface.tsx`

- [ ] **Step 1: Vendor liquidgl.js into `frontend/public/vendor/liquidgl.js`**

Since `naughtyduk/liquidGL` is a GitHub library (not npm), download the latest `liquidgl.min.js` from the project's `dist/` folder and save it to `frontend/public/vendor/liquidgl.js`.

```bash
mkdir -p frontend/public/vendor
curl -L -o frontend/public/vendor/liquidgl.js \
  https://raw.githubusercontent.com/naughtyduk/liquidGL/main/dist/liquidgl.min.js
test -s frontend/public/vendor/liquidgl.js && echo "OK file present"
```

Expected: `OK file present`.

- [ ] **Step 2: Create `frontend/src/design/LiquidGLSurface.tsx`**

```tsx
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

declare global {
  interface Window {
    LiquidGL?: {
      init: (opts: {
        container: HTMLElement;
        refraction?: number;
        dispersion?: number;
        blur?: number;
        tint?: string;
      }) => { destroy: () => void };
    };
  }
}

interface Props {
  children: ReactNode;
  refraction?: number;
  dispersion?: number;
  blur?: number;
  tint?: string;
  className?: string;
  fallbackClassName?: string;
}

let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.LiquidGL) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/vendor/liquidgl.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("liquidgl failed to load"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export function LiquidGLSurface({
  children,
  refraction = 0.04,
  dispersion = 0.015,
  blur = 6,
  tint = "rgba(255,255,255,0.02)",
  className,
  fallbackClassName,
}: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let cancelled = false;
    const prefersReduced =
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;

    loadScript()
      .then(() => {
        if (cancelled || !ref.current || !window.LiquidGL) return;
        const instance = window.LiquidGL.init({
          container: ref.current,
          refraction,
          dispersion,
          blur,
          tint,
        });
        cleanup = () => instance.destroy();
      })
      .catch(() => {
        /* fallback stays visible */
      });
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [refraction, dispersion, blur, tint]);

  return (
    <div
      ref={ref}
      className={cn(
        "relative rounded-xl border border-border glass-edge",
        "bg-surface-strong backdrop-blur-xl",
        fallbackClassName,
        className
      )}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Verify asset is served by dev server**

```bash
cd frontend && npm run dev -- --port 5173 &
sleep 3
curl -sI http://127.0.0.1:5173/vendor/liquidgl.js | head -1
kill %1 2>/dev/null || true
```

Expected: `HTTP/1.1 200 OK`.

- [ ] **Step 4: Commit**

```bash
git add frontend/public/vendor/liquidgl.js frontend/src/design/LiquidGLSurface.tsx
git commit -m "Vendor liquidgl and add LiquidGLSurface component with graceful fallback"
```

---

## Task 10: AppShell, Header, NavBar

**Files:**
- Replace: `frontend/src/layout/AppShell.tsx`
- Create: `frontend/src/layout/Header.tsx`
- Create: `frontend/src/layout/NavBar.tsx`

- [ ] **Step 1: Create `frontend/src/layout/NavBar.tsx`**

```tsx
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";

const items = [
  { to: "/discover", label: "Discover" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/for-you", label: "For you" },
  { to: "/chat", label: "Chat" },
];

export function NavBar() {
  return (
    <nav className="flex items-center gap-1 text-sm">
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          className={({ isActive }) =>
            cn(
              "relative px-3 py-1.5 rounded-md text-text-muted transition-colors",
              "hover:text-text hover:bg-white/[0.04]",
              isActive && "text-text bg-white/[0.06]"
            )
          }
        >
          {it.label}
        </NavLink>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Create `frontend/src/layout/Header.tsx`**

```tsx
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";
import { NavBar } from "./NavBar";

export function Header() {
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-30 px-6 py-3 border-b border-border/60 bg-bg/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto flex items-center gap-6">
        <Link to="/" className="font-display text-lg text-amber tracking-tight">
          Bingery
        </Link>
        <NavBar />
        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <>
              <span className="hidden md:inline text-sm text-text-muted">
                {user.display_name ?? user.username}
              </span>
              <Button variant="ghost" size="sm" onClick={signOut}>
                Sign out
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => navigate("/auth")}>
              Sign in
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Replace `frontend/src/layout/AppShell.tsx`**

```tsx
import { Outlet } from "react-router-dom";
import { AmbientBlobs } from "@/design/AmbientBlobs";
import { GrainOverlay } from "@/design/GrainOverlay";
import { Header } from "./Header";

export default function AppShell() {
  return (
    <div className="relative min-h-screen bg-bg text-text">
      <AmbientBlobs />
      <GrainOverlay />
      <div className="relative z-10">
        <Header />
        <main className="max-w-7xl mx-auto px-6 py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Visually verify shell boots**

```bash
cd frontend && npm run dev -- --port 5173 &
sleep 3
curl -s http://127.0.0.1:5173/ | grep -q "root" && echo "OK"
kill %1 2>/dev/null || true
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layout/AppShell.tsx frontend/src/layout/Header.tsx frontend/src/layout/NavBar.tsx
git commit -m "Add AppShell with ambient blobs, grain, sticky header, nav bar"
```

---

## Task 11: Landing page

**Files:**
- Create: `frontend/src/features/landing/LandingPage.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/features/landing/LandingPage.tsx`**

```tsx
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { LiquidGLSurface } from "@/design/LiquidGLSurface";
import { Button } from "@/design/Button";
import { fadeInUp, transitions } from "@/design/motion";

export function LandingPage() {
  return (
    <section className="flex flex-col items-center text-center gap-10 py-16">
      <motion.div
        variants={fadeInUp}
        initial="hidden"
        animate="show"
        transition={transitions.easeSlow}
        className="flex flex-col items-center gap-5 max-w-2xl"
      >
        <span className="text-xs tracking-[0.3em] text-amber uppercase font-mono">
          Anime, quietly curated
        </span>
        <h1 className="font-display text-6xl md:text-7xl leading-[1.02]">
          Discover what you’ll
          <span className="block italic text-amber">actually love.</span>
        </h1>
        <p className="text-text-muted max-w-xl">
          A dark, unhurried space to rate, collect, and find your next favorite
          series — backed by a taste model that listens.
        </p>
        <div className="flex gap-3">
          <Link to="/discover">
            <Button size="lg">Start browsing</Button>
          </Link>
          <Link to="/chat">
            <Button size="lg" variant="ghost">
              Ask the guide
            </Button>
          </Link>
        </div>
      </motion.div>

      <motion.div
        variants={fadeInUp}
        initial="hidden"
        animate="show"
        transition={{ ...transitions.easeSlow, delay: 0.15 }}
        className="w-full max-w-5xl"
      >
        <LiquidGLSurface className="p-8 md:p-12">
          <div className="grid md:grid-cols-3 gap-6 text-left">
            <Feature
              title="Rate"
              body="Ten-point ratings with optional reviews and fan-genre votes."
            />
            <Feature
              title="Track"
              body="Watching, plan to watch, on hold, dropped — or keep it private."
            />
            <Feature
              title="Find"
              body="A Claude or local-model guide tuned to your taste."
            />
          </div>
        </LiquidGLSurface>
      </motion.div>
    </section>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h3 className="font-display text-2xl text-amber mb-2">{title}</h3>
      <p className="text-text-muted">{body}</p>
    </div>
  );
}
```

- [ ] **Step 2: Wire into router — modify `frontend/src/routes.tsx`**

Open the file and replace the `{ index: true, element: <Placeholder name="Landing" /> }` line with:

```tsx
      { index: true, element: <LandingPage /> },
```

Add the import at the top of the file (near other imports):

```tsx
import { LandingPage } from "@/features/landing/LandingPage";
```

- [ ] **Step 3: Dev server visual check**

```bash
cd frontend && npm run dev -- --port 5173 &
sleep 3
curl -s http://127.0.0.1:5173/ | grep -q "Bingery" && echo "OK"
kill %1 2>/dev/null || true
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/landing/LandingPage.tsx frontend/src/routes.tsx
git commit -m "Add landing page with liquid-glass hero and CTA"
```

---

## Task 12: Auth page (login + register)

**Files:**
- Create: `frontend/src/features/auth/AuthForm.tsx`
- Create: `frontend/src/features/auth/AuthPage.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/features/auth/AuthForm.tsx`**

```tsx
import { useState } from "react";
import { Input } from "@/design/Input";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";

type Mode = "login" | "register";

export function AuthForm({ onSuccess }: { onSuccess?: () => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const signIn = useAuth((s) => s.signIn);
  const signUp = useAuth((s) => s.signUp);

  const submit = async () => {
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") await signIn({ email, password });
      else await signUp({ email, password, username });
      onSuccess?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="flex flex-col gap-4"
    >
      <div className="flex gap-2 text-sm">
        <button
          type="button"
          onClick={() => setMode("login")}
          className={
            "px-3 py-1.5 rounded-md " +
            (mode === "login"
              ? "bg-white/[0.08] text-text"
              : "text-text-muted hover:text-text")
          }
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => setMode("register")}
          className={
            "px-3 py-1.5 rounded-md " +
            (mode === "register"
              ? "bg-white/[0.08] text-text"
              : "text-text-muted hover:text-text")
          }
        >
          Create account
        </button>
      </div>

      {mode === "register" ? (
        <Input
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
      ) : null}
      <Input
        label="Email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        autoComplete="email"
        required
      />
      <Input
        label="Password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        required
      />
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Button type="submit" loading={loading}>
        {mode === "login" ? "Sign in" : "Create account"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 2: Create `frontend/src/features/auth/AuthPage.tsx`**

```tsx
import { useNavigate } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { AuthForm } from "./AuthForm";

export function AuthPage() {
  const navigate = useNavigate();
  return (
    <div className="max-w-md mx-auto mt-8">
      <GlassCard tone="warm" className="p-8" elevated>
        <h1 className="font-display text-3xl mb-1">Welcome back</h1>
        <p className="text-text-muted mb-6">
          Sign in to rate, collect, and chat with your taste guide.
        </p>
        <AuthForm onSuccess={() => navigate("/discover")} />
      </GlassCard>
    </div>
  );
}
```

- [ ] **Step 3: Wire into router**

In `frontend/src/routes.tsx`, add import and replace the auth placeholder:

```tsx
import { AuthPage } from "@/features/auth/AuthPage";
```

Replace `{ path: "auth", element: <Placeholder name="Auth" /> }` with:

```tsx
      { path: "auth", element: <AuthPage /> },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/auth/AuthForm.tsx frontend/src/features/auth/AuthPage.tsx frontend/src/routes.tsx
git commit -m "Add auth page with sign-in and register flow"
```

---

## Task 13: AnimeCard + AnimeGrid + query hooks

**Files:**
- Create: `frontend/src/hooks/useAnimeList.ts`
- Create: `frontend/src/features/discover/AnimeCard.tsx`
- Create: `frontend/src/features/discover/AnimeGrid.tsx`
- Create: `frontend/tests/features/AnimeCard.test.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useAnimeList.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Params {
  page?: number;
  perPage?: number;
  search?: string;
  genre?: string;
  sort?: string;
  order?: "asc" | "desc";
}

export function useAnimeList(params: Params = {}) {
  const {
    page = 1,
    perPage = 24,
    search = "",
    genre = "",
    sort = "api_score",
    order = "desc",
  } = params;
  const qs = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    sort,
    order,
  });
  if (search) qs.set("search", search);
  if (genre) qs.set("genre", genre);
  const key = ["anime-list", page, perPage, search, genre, sort, order];
  return useQuery({
    queryKey: key,
    queryFn: () => api.getAnime("?" + qs.toString()),
  });
}
```

- [ ] **Step 2: Create `frontend/src/features/discover/AnimeCard.tsx`**

```tsx
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { AnimeSummary } from "@/types/models";
import { Badge } from "@/design/Badge";
import { cn } from "@/lib/cn";
import { genreColor } from "@/lib/genres";
import { transitions } from "@/design/motion";

interface Props {
  anime: AnimeSummary;
  index?: number;
  compact?: boolean;
}

export function AnimeCard({ anime, index = 0, compact }: Props) {
  const score = anime.community_score ?? anime.api_score;
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g: { name?: string } | string) => (typeof g === "string" ? g : g.name ?? ""))
    .filter(Boolean)
    .slice(0, 3);
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...transitions.ease, delay: Math.min(index, 10) * 0.02 }}
    >
      <Link
        to={`/anime/${anime.id}`}
        className={cn(
          "group block rounded-lg overflow-hidden border border-border",
          "bg-surface hover:border-border-strong transition-colors",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50"
        )}
      >
        <div
          className={cn(
            "relative bg-black/40 overflow-hidden",
            compact ? "aspect-[3/4]" : "aspect-[2/3]"
          )}
        >
          {anime.image_url ? (
            <img
              src={anime.image_url}
              alt={anime.title}
              loading="lazy"
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-dim text-xs">
              No image
            </div>
          )}
          {score ? (
            <span className="absolute top-2 right-2 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur-md text-xs font-mono text-amber">
              {Number(score).toFixed(1)}
            </span>
          ) : null}
        </div>
        <div className="p-3">
          <h3 className="text-sm font-semibold line-clamp-2 mb-1.5">
            {anime.title_english ?? anime.title}
          </h3>
          <div className="flex flex-wrap gap-1">
            {genres.map((g) => (
              <Badge key={g} color={genreColor(g)}>
                {g}
              </Badge>
            ))}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/discover/AnimeGrid.tsx`**

```tsx
import type { AnimeSummary } from "@/types/models";
import { Skeleton } from "@/design/Skeleton";
import { AnimeCard } from "./AnimeCard";

interface Props {
  anime: AnimeSummary[];
  loading?: boolean;
  empty?: React.ReactNode;
}

export function AnimeGrid({ anime, loading, empty }: Props) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="aspect-[2/3]" rounded="lg" />
            <Skeleton className="h-3 mt-2 w-3/4" />
          </div>
        ))}
      </div>
    );
  }
  if (!anime.length) {
    return (
      <div className="py-24 text-center text-text-muted">
        {empty ?? "No anime found."}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
      {anime.map((a, i) => (
        <AnimeCard key={a.id} anime={a} index={i} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Write the test — `frontend/tests/features/AnimeCard.test.tsx`**

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AnimeCard } from "@/features/discover/AnimeCard";

const sample = {
  id: 42,
  anilist_id: 1,
  title: "Sample Anime",
  title_english: "Sample Anime EN",
  title_japanese: null,
  description: null,
  image_url: "https://example.com/x.jpg",
  banner_url: null,
  episodes: 12,
  season: null,
  year: 2024,
  format: null,
  status: null,
  api_score: 7.8,
  community_score: null,
  rating_count: null,
  genres: [{ name: "Action" }, { name: "Fantasy" }],
};

describe("AnimeCard", () => {
  it("renders title, score, and genres", () => {
    render(
      <MemoryRouter>
        <AnimeCard anime={sample} />
      </MemoryRouter>
    );
    expect(screen.getByText("Sample Anime EN")).toBeInTheDocument();
    expect(screen.getByText("7.8")).toBeInTheDocument();
    expect(screen.getByText("Action")).toBeInTheDocument();
    expect(screen.getByText("Fantasy")).toBeInTheDocument();
  });

  it("links to detail page", () => {
    render(
      <MemoryRouter>
        <AnimeCard anime={sample} />
      </MemoryRouter>
    );
    expect(screen.getByRole("link")).toHaveAttribute("href", "/anime/42");
  });
});
```

- [ ] **Step 5: Run test**

```bash
cd frontend && npx vitest run tests/features/AnimeCard.test.tsx
```

Expected: PASS — 2 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useAnimeList.ts frontend/src/features/discover/AnimeCard.tsx frontend/src/features/discover/AnimeGrid.tsx frontend/tests/features/AnimeCard.test.tsx
git commit -m "Add AnimeCard, AnimeGrid, and useAnimeList query hook"
```

---

## Task 14: Discover page + FilterBar + SearchAutocomplete

**Files:**
- Create: `frontend/src/features/discover/SearchAutocomplete.tsx`
- Create: `frontend/src/features/discover/FilterBar.tsx`
- Create: `frontend/src/features/discover/DiscoverPage.tsx`
- Create: `frontend/src/hooks/useSearch.ts`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useSearch.ts`**

```ts
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AnimeSummary } from "@/types/models";

export function useSearch(query: string, minChars = 2, delay = 250) {
  const [results, setResults] = useState<AnimeSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.length < minChars) {
      setResults([]);
      return;
    }
    setLoading(true);
    const id = setTimeout(() => {
      api
        .autocomplete(query)
        .then((r) => setResults(r.results ?? []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, delay);
    return () => clearTimeout(id);
  }, [query, minChars, delay]);

  return { results, loading };
}
```

- [ ] **Step 2: Create `frontend/src/features/discover/SearchAutocomplete.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Input } from "@/design/Input";
import { useSearch } from "@/hooks/useSearch";
import { transitions } from "@/design/motion";

interface Props {
  onSubmit?: (q: string) => void;
}

export function SearchAutocomplete({ onSubmit }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement | null>(null);
  const { results, loading } = useSearch(q);
  const nav = useNavigate();

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div ref={wrap} className="relative flex-1 max-w-xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) {
            setOpen(false);
            onSubmit?.(q.trim());
          }
        }}
      >
        <Input
          placeholder="Search anime…"
          value={q}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
        />
      </form>
      <AnimatePresence>
        {open && (results.length > 0 || loading) ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={transitions.easeFast}
            className="absolute left-0 right-0 mt-2 rounded-lg border border-border bg-bg-elevated/95 backdrop-blur-xl overflow-hidden z-20 glass-edge"
          >
            {loading ? (
              <div className="p-3 text-sm text-text-muted">Searching…</div>
            ) : (
              results.slice(0, 8).map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    setQ("");
                    nav(`/anime/${a.id}`);
                  }}
                  className="flex gap-3 w-full text-left p-2 hover:bg-white/[0.05]"
                >
                  {a.image_url ? (
                    <img
                      src={a.image_url}
                      alt=""
                      className="w-10 h-14 object-cover rounded"
                    />
                  ) : (
                    <div className="w-10 h-14 rounded bg-white/5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">
                      {a.title_english ?? a.title}
                    </div>
                    <div className="text-xs text-text-muted truncate">
                      {a.year ?? ""} {a.format ?? ""}
                    </div>
                  </div>
                </button>
              ))
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/discover/FilterBar.tsx`**

```tsx
import { FAN_GENRES, genreColor } from "@/lib/genres";
import { cn } from "@/lib/cn";

interface Props {
  genre: string;
  onGenre: (g: string) => void;
  sort: string;
  onSort: (s: string) => void;
}

const sorts: Array<{ key: string; label: string }> = [
  { key: "api_score", label: "API score" },
  { key: "community_score", label: "Community score" },
  { key: "year", label: "Year" },
  { key: "title", label: "Title" },
];

export function FilterBar({ genre, onGenre, sort, onSort }: Props) {
  return (
    <div className="flex flex-col gap-3 mb-6">
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        <button
          onClick={() => onGenre("")}
          className={cn(
            "shrink-0 px-3 py-1.5 rounded-full text-xs border",
            genre === ""
              ? "bg-amber text-bg border-amber"
              : "border-border text-text-muted hover:text-text hover:border-border-strong"
          )}
        >
          All
        </button>
        {FAN_GENRES.map((g) => {
          const active = genre === g;
          return (
            <button
              key={g}
              onClick={() => onGenre(g)}
              className={cn(
                "shrink-0 px-3 py-1.5 rounded-full text-xs border transition-colors",
                active
                  ? "border-transparent text-bg"
                  : "border-border text-text-muted hover:text-text hover:border-border-strong"
              )}
              style={active ? { background: genreColor(g) } : undefined}
            >
              {g}
            </button>
          );
        })}
      </div>
      <div className="flex items-center gap-2 text-sm">
        <span className="text-text-muted">Sort by</span>
        {sorts.map((s) => (
          <button
            key={s.key}
            onClick={() => onSort(s.key)}
            className={cn(
              "px-2 py-1 rounded-md",
              sort === s.key
                ? "text-text bg-white/[0.06]"
                : "text-text-muted hover:text-text"
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/features/discover/DiscoverPage.tsx`**

```tsx
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAnimeList } from "@/hooks/useAnimeList";
import { AnimeGrid } from "./AnimeGrid";
import { FilterBar } from "./FilterBar";
import { SearchAutocomplete } from "./SearchAutocomplete";

export function DiscoverPage() {
  const [params, setParams] = useSearchParams();
  const search = params.get("q") ?? "";
  const genre = params.get("genre") ?? "";
  const sort = params.get("sort") ?? "api_score";
  const [page, setPage] = useState(1);

  const { data, isLoading, isFetching } = useAnimeList({
    page,
    search,
    genre,
    sort,
  });

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
    setPage(1);
  };

  return (
    <div>
      <div className="flex flex-col md:flex-row gap-4 mb-6 items-start md:items-center">
        <h1 className="font-display text-4xl text-amber">Discover</h1>
        <div className="flex-1 md:ml-auto md:max-w-xl">
          <SearchAutocomplete
            onSubmit={(q) => update("q", q)}
          />
        </div>
      </div>
      <FilterBar
        genre={genre}
        onGenre={(g) => update("genre", g)}
        sort={sort}
        onSort={(s) => update("sort", s)}
      />
      <AnimeGrid anime={data?.anime ?? []} loading={isLoading} />
      {data && data.pages > 1 ? (
        <div className="flex justify-center items-center gap-3 mt-8 text-sm">
          <Button
            variant="ghost"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="text-text-muted tabular-nums">
            {data.page} / {data.pages}
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={page >= data.pages || isFetching}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Wire into router**

In `frontend/src/routes.tsx`, add import and replace discover placeholder:

```tsx
import { DiscoverPage } from "@/features/discover/DiscoverPage";
```

Replace `{ path: "discover", element: <Placeholder name="Discover" /> }` with:

```tsx
      { path: "discover", element: <DiscoverPage /> },
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useSearch.ts frontend/src/features/discover/SearchAutocomplete.tsx frontend/src/features/discover/FilterBar.tsx frontend/src/features/discover/DiscoverPage.tsx frontend/src/routes.tsx
git commit -m "Add Discover page with filter bar, search autocomplete, pagination"
```

---

## Task 15: Anime detail page with hero, rating panel, fan genres, similar

**Files:**
- Create: `frontend/src/hooks/useAnimeDetail.ts`
- Create: `frontend/src/hooks/useRatings.ts`
- Create: `frontend/src/features/details/DetailHero.tsx`
- Create: `frontend/src/features/details/RatingPanel.tsx`
- Create: `frontend/src/features/details/FanGenreBars.tsx`
- Create: `frontend/src/features/details/SimilarStrip.tsx`
- Create: `frontend/src/features/details/AnimeDetailPage.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useAnimeDetail.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useAnimeDetail(id: number | undefined) {
  return useQuery({
    queryKey: ["anime-detail", id],
    queryFn: () => api.getAnimeDetail(id!),
    enabled: !!id,
  });
}

export function useSimilar(id: number | undefined) {
  return useQuery({
    queryKey: ["anime-similar", id],
    queryFn: () => api.getSimilar(id!),
    enabled: !!id,
  });
}
```

- [ ] **Step 2: Create `frontend/src/hooks/useRatings.ts`**

```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useSubmitReview(animeId: number | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { score: number; review?: string; genres?: string[] }) =>
      api.submitReview(animeId!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["anime-detail", animeId] });
    },
  });
}
```

- [ ] **Step 3: Create `frontend/src/features/details/DetailHero.tsx`**

```tsx
import type { AnimeDetail } from "@/types/models";
import { LiquidGLSurface } from "@/design/LiquidGLSurface";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

export function DetailHero({ anime }: { anime: AnimeDetail }) {
  const genres = (anime.official_genres ?? anime.genres ?? [])
    .map((g) => (typeof g === "string" ? g : g.name))
    .filter(Boolean) as string[];
  return (
    <div className="relative overflow-hidden rounded-xl mb-6">
      {anime.banner_url ? (
        <img
          src={anime.banner_url}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-25"
        />
      ) : null}
      <div className="absolute inset-0 bg-gradient-to-t from-bg via-bg/80 to-transparent" />
      <LiquidGLSurface className="relative z-10 p-6 md:p-10 flex flex-col md:flex-row gap-6">
        {anime.image_url ? (
          <img
            src={anime.image_url}
            alt=""
            className="w-40 md:w-56 aspect-[2/3] rounded-lg object-cover shrink-0 shadow-2xl"
          />
        ) : null}
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-4xl md:text-5xl mb-2">
            {anime.title_english ?? anime.title}
          </h1>
          {anime.title_english && anime.title !== anime.title_english ? (
            <p className="text-text-muted mb-3">{anime.title}</p>
          ) : null}
          <div className="flex flex-wrap gap-1.5 mb-4">
            {genres.slice(0, 6).map((g) => (
              <Badge key={g} color={genreColor(g)}>
                {g}
              </Badge>
            ))}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Stat label="Episodes" value={anime.episodes ?? "—"} />
            <Stat label="Year" value={anime.year ?? "—"} />
            <Stat label="Format" value={anime.format ?? "—"} />
            <Stat label="Score" value={anime.api_score?.toFixed(1) ?? "—"} />
          </div>
          {anime.description ? (
            <p className="mt-5 text-text-muted leading-relaxed max-w-3xl">
              {anime.description.replace(/<[^>]+>/g, "")}
            </p>
          ) : null}
        </div>
      </LiquidGLSurface>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs text-text-dim uppercase tracking-wider">{label}</div>
      <div className="text-lg font-mono text-amber">{value}</div>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/features/details/FanGenreBars.tsx`**

```tsx
import type { FanGenre } from "@/types/models";
import { genreColor } from "@/lib/genres";

export function FanGenreBars({ fanGenres }: { fanGenres: FanGenre[] }) {
  if (!fanGenres.length) return null;
  const max = fanGenres[0]?.votes || 1;
  return (
    <div className="space-y-2">
      {fanGenres.map((g) => {
        const w = (g.votes / max) * 100;
        const c = genreColor(g.genre);
        return (
          <div key={g.genre} className="flex items-center gap-3 text-sm">
            <div className="w-32 shrink-0 text-text-muted">{g.genre}</div>
            <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${w}%`, background: c }}
              />
            </div>
            <div className="w-10 text-right font-mono text-text-muted tabular-nums">
              {g.votes}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: Create `frontend/src/features/details/RatingPanel.tsx`**

```tsx
import { useEffect, useState } from "react";
import type { AnimeDetail } from "@/types/models";
import { StarRating } from "@/design/StarRating";
import { Button } from "@/design/Button";
import { FAN_GENRES, genreColor } from "@/lib/genres";
import { cn } from "@/lib/cn";
import { useSubmitReview } from "@/hooks/useRatings";
import { useAuth } from "@/stores/auth";

export function RatingPanel({ anime }: { anime: AnimeDetail }) {
  const user = useAuth((s) => s.user);
  const [score, setScore] = useState(anime.user_rating?.score ?? 0);
  const [review, setReview] = useState(anime.user_rating?.review ?? "");
  const [fgs, setFgs] = useState<string[]>(anime.user_genre_votes ?? []);
  const [saved, setSaved] = useState(false);
  const submit = useSubmitReview(anime.id);

  useEffect(() => {
    setScore(anime.user_rating?.score ?? 0);
    setReview(anime.user_rating?.review ?? "");
    setFgs(anime.user_genre_votes ?? []);
  }, [anime.id]);

  if (!user) {
    return (
      <p className="text-sm text-text-muted">
        Sign in to rate, review, and vote on fan-genres.
      </p>
    );
  }

  const toggle = (g: string) =>
    setFgs((prev) =>
      prev.includes(g) ? prev.filter((x) => x !== g) : prev.length < 15 ? [...prev, g] : prev
    );

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm text-text-muted block mb-2">Your rating</label>
        <StarRating value={score} onChange={setScore} />
      </div>
      <div>
        <label className="text-sm text-text-muted block mb-2">
          Short review (optional)
        </label>
        <textarea
          value={review}
          onChange={(e) => {
            setReview(e.target.value);
            setSaved(false);
          }}
          placeholder="What did you think?"
          className="w-full min-h-[80px] px-3 py-2 rounded-lg bg-surface border border-border focus:border-border-strong outline-none text-sm font-sans"
        />
      </div>
      <div>
        <label className="text-sm text-text-muted block mb-2">
          Fan-genre votes <span className="text-text-dim">({fgs.length}/15)</span>
        </label>
        <div className="flex flex-wrap gap-1.5">
          {FAN_GENRES.map((g) => {
            const active = fgs.includes(g);
            return (
              <button
                key={g}
                onClick={() => toggle(g)}
                className={cn(
                  "px-3 py-1 rounded-full text-xs border transition-colors",
                  active
                    ? "border-transparent text-bg"
                    : "border-border text-text-muted hover:border-border-strong"
                )}
                style={active ? { background: genreColor(g) } : undefined}
              >
                {g}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button
          onClick={() =>
            submit
              .mutateAsync({ score, review, genres: fgs })
              .then(() => {
                setSaved(true);
                setTimeout(() => setSaved(false), 1800);
              })
          }
          loading={submit.isPending}
          disabled={score === 0}
        >
          {saved ? "Saved" : "Save rating"}
        </Button>
        {submit.isError ? (
          <span className="text-sm text-danger">
            {(submit.error as Error).message}
          </span>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create `frontend/src/features/details/SimilarStrip.tsx`**

```tsx
import type { AnimeSummary } from "@/types/models";
import { AnimeCard } from "@/features/discover/AnimeCard";

export function SimilarStrip({ similar }: { similar: AnimeSummary[] }) {
  if (!similar.length) return null;
  return (
    <section className="mt-10">
      <h2 className="font-display text-2xl mb-4">You might also like</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {similar.slice(0, 6).map((a, i) => (
          <AnimeCard key={a.id} anime={a} index={i} />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Create `frontend/src/features/details/AnimeDetailPage.tsx`**

```tsx
import { useParams } from "react-router-dom";
import { GlassCard } from "@/design/GlassCard";
import { Skeleton } from "@/design/Skeleton";
import { useAnimeDetail, useSimilar } from "@/hooks/useAnimeDetail";
import { DetailHero } from "./DetailHero";
import { FanGenreBars } from "./FanGenreBars";
import { RatingPanel } from "./RatingPanel";
import { SimilarStrip } from "./SimilarStrip";

export function AnimeDetailPage() {
  const { id } = useParams();
  const numericId = id ? Number(id) : undefined;
  const detail = useAnimeDetail(numericId);
  const similar = useSimilar(numericId);

  if (detail.isLoading || !detail.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-72" rounded="lg" />
        <Skeleton className="h-48" rounded="lg" />
      </div>
    );
  }
  const anime = detail.data.anime;
  return (
    <article>
      <DetailHero anime={anime} />
      <div className="grid md:grid-cols-[1fr_420px] gap-8">
        <section>
          <h2 className="font-display text-2xl mb-4">Community fan genres</h2>
          <GlassCard className="p-6">
            {anime.fan_genres && anime.fan_genres.length ? (
              <FanGenreBars fanGenres={anime.fan_genres} />
            ) : (
              <p className="text-text-muted text-sm">
                No fan-genre votes yet. Be the first.
              </p>
            )}
          </GlassCard>
        </section>
        <aside>
          <h2 className="font-display text-2xl mb-4">Your rating</h2>
          <GlassCard tone="warm" className="p-6">
            <RatingPanel anime={anime} />
          </GlassCard>
        </aside>
      </div>
      <SimilarStrip similar={similar.data?.similar ?? []} />
    </article>
  );
}
```

- [ ] **Step 8: Wire into router**

In `frontend/src/routes.tsx`, add import and replace detail placeholder:

```tsx
import { AnimeDetailPage } from "@/features/details/AnimeDetailPage";
```

Replace `{ path: "anime/:id", element: <Placeholder name="Anime detail" /> }` with:

```tsx
      { path: "anime/:id", element: <AnimeDetailPage /> },
```

- [ ] **Step 9: Commit**

```bash
git add frontend/src/hooks/useAnimeDetail.ts frontend/src/hooks/useRatings.ts frontend/src/features/details/DetailHero.tsx frontend/src/features/details/RatingPanel.tsx frontend/src/features/details/FanGenreBars.tsx frontend/src/features/details/SimilarStrip.tsx frontend/src/features/details/AnimeDetailPage.tsx frontend/src/routes.tsx
git commit -m "Add anime detail page with hero, rating panel, fan genres, similar strip"
```

---

## Task 16: Watchlist page

**Files:**
- Create: `frontend/src/hooks/useWatchlist.ts`
- Create: `frontend/src/features/watchlist/StatusTabs.tsx`
- Create: `frontend/src/features/watchlist/WatchStatusSelector.tsx`
- Create: `frontend/src/features/watchlist/WatchlistPage.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useWatchlist.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { WatchStatus } from "@/types/models";

export function useWatchlist(status?: WatchStatus) {
  return useQuery({
    queryKey: ["watchlist", status ?? "all"],
    queryFn: () => api.getWatchlist(status ? `?status=${status}` : ""),
  });
}

export function useWatchlistStats() {
  return useQuery({
    queryKey: ["watchlist-stats"],
    queryFn: () => api.getWatchlistStats(),
  });
}

export function useSetWatchStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      animeId,
      status,
    }: {
      animeId: number;
      status: WatchStatus;
    }) => api.setWatchStatus(animeId, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
    },
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.toggleFavorite(animeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
    },
  });
}

export function useRemoveFromWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (animeId: number) => api.removeFromWatchlist(animeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      qc.invalidateQueries({ queryKey: ["watchlist-stats"] });
    },
  });
}
```

- [ ] **Step 2: Create `frontend/src/features/watchlist/StatusTabs.tsx`**

```tsx
import type { WatchStatus } from "@/types/models";
import type { WatchStats } from "@/types/models";
import { cn } from "@/lib/cn";

export const STATUSES: Array<{ key: WatchStatus; label: string; color: string }> = [
  { key: "watching", label: "Watching", color: "#3b82f6" },
  { key: "completed", label: "Completed", color: "#22c55e" },
  { key: "plan_to_watch", label: "Plan to Watch", color: "#f59e0b" },
  { key: "on_hold", label: "On Hold", color: "#8b5cf6" },
  { key: "dropped", label: "Dropped", color: "#ef4444" },
];

interface Props {
  stats?: WatchStats;
  value: WatchStatus | null;
  onChange: (s: WatchStatus | null) => void;
}

export function StatusTabs({ stats, value, onChange }: Props) {
  const counts: Record<string, number> = stats
    ? (stats as unknown as Record<string, number>)
    : {};
  const total = STATUSES.reduce((n, s) => n + (counts[s.key] ?? 0), 0);
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 mb-6">
      <button
        onClick={() => onChange(null)}
        className={cn(
          "shrink-0 px-4 py-2 rounded-full text-sm border",
          value === null
            ? "bg-amber text-bg border-amber"
            : "border-border text-text-muted hover:text-text hover:border-border-strong"
        )}
      >
        All <span className="ml-1 text-xs tabular-nums opacity-70">{total}</span>
      </button>
      {STATUSES.map((s) => {
        const n = counts[s.key] ?? 0;
        const active = value === s.key;
        return (
          <button
            key={s.key}
            onClick={() => onChange(s.key)}
            className={cn(
              "shrink-0 px-4 py-2 rounded-full text-sm border transition-colors",
              active
                ? "border-transparent text-bg"
                : "border-border text-text-muted hover:text-text hover:border-border-strong"
            )}
            style={active ? { background: s.color } : undefined}
          >
            {s.label}
            <span className="ml-1 text-xs tabular-nums opacity-70">{n}</span>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/watchlist/WatchStatusSelector.tsx`**

```tsx
import { useState } from "react";
import type { WatchStatus } from "@/types/models";
import { Button } from "@/design/Button";
import { STATUSES } from "./StatusTabs";
import {
  useRemoveFromWatchlist,
  useSetWatchStatus,
  useToggleFavorite,
} from "@/hooks/useWatchlist";

interface Props {
  animeId: number;
  current: WatchStatus | null;
  isFavorite: boolean;
}

export function WatchStatusSelector({ animeId, current, isFavorite }: Props) {
  const [open, setOpen] = useState(false);
  const setStatus = useSetWatchStatus();
  const toggleFav = useToggleFavorite();
  const remove = useRemoveFromWatchlist();

  const curMeta = STATUSES.find((s) => s.key === current);

  return (
    <div className="relative inline-flex items-center gap-2">
      <Button
        size="sm"
        variant={current ? "glass" : "primary"}
        onClick={() => setOpen((o) => !o)}
      >
        {curMeta?.label ?? "Add to watchlist"}
      </Button>
      <Button
        size="sm"
        variant={isFavorite ? "primary" : "ghost"}
        onClick={() => toggleFav.mutate(animeId)}
        aria-label="Favorite"
      >
        {isFavorite ? "★" : "☆"}
      </Button>
      {open ? (
        <div className="absolute top-full mt-2 left-0 z-10 flex flex-col gap-1 p-2 rounded-lg bg-bg-elevated border border-border glass-edge min-w-[180px]">
          {STATUSES.map((s) => (
            <button
              key={s.key}
              onClick={() => {
                setStatus.mutate({ animeId, status: s.key });
                setOpen(false);
              }}
              className="text-left text-sm px-3 py-2 rounded-md hover:bg-white/[0.05]"
              style={{ color: s.color }}
            >
              {s.label}
            </button>
          ))}
          {current ? (
            <button
              onClick={() => {
                remove.mutate(animeId);
                setOpen(false);
              }}
              className="text-left text-sm px-3 py-2 rounded-md hover:bg-white/[0.05] text-danger"
            >
              Remove from list
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/features/watchlist/WatchlistPage.tsx`**

```tsx
import { useState } from "react";
import type { WatchStatus } from "@/types/models";
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { StatusTabs } from "./StatusTabs";
import { useAuth } from "@/stores/auth";
import { useWatchlist, useWatchlistStats } from "@/hooks/useWatchlist";

export function WatchlistPage() {
  const user = useAuth((s) => s.user);
  const [status, setStatus] = useState<WatchStatus | null>(null);
  const wl = useWatchlist(status ?? undefined);
  const stats = useWatchlistStats();

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in to track</h1>
        <p className="text-text-muted">
          Your watching, completed, and plan-to-watch list lives here.
        </p>
      </div>
    );
  }

  const items = (wl.data?.entries ?? []).map((e) => e.anime);

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-5">Your watchlist</h1>
      <StatusTabs stats={stats.data?.stats} value={status} onChange={setStatus} />
      <AnimeGrid
        anime={items}
        loading={wl.isLoading}
        empty="Nothing here yet — add anime from the discover page."
      />
    </div>
  );
}
```

- [ ] **Step 5: Wire into router**

In `frontend/src/routes.tsx`, add import and replace watchlist placeholder:

```tsx
import { WatchlistPage } from "@/features/watchlist/WatchlistPage";
```

Replace `{ path: "watchlist", element: <Placeholder name="Watchlist" /> }` with:

```tsx
      { path: "watchlist", element: <WatchlistPage /> },
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useWatchlist.ts frontend/src/features/watchlist/StatusTabs.tsx frontend/src/features/watchlist/WatchStatusSelector.tsx frontend/src/features/watchlist/WatchlistPage.tsx frontend/src/routes.tsx
git commit -m "Add watchlist page with status tabs and CRUD mutations"
```

---

## Task 17: For-you page with taste profile

**Files:**
- Create: `frontend/src/hooks/useRecommendations.ts`
- Create: `frontend/src/features/for-you/TasteProfile.tsx`
- Create: `frontend/src/features/for-you/ForYouPage.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useRecommendations.ts`**

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRecommendations(enabled: boolean) {
  return useQuery({
    queryKey: ["recommendations"],
    queryFn: () => api.getRecs(),
    enabled,
    staleTime: 5 * 60_000,
  });
}
```

- [ ] **Step 2: Create `frontend/src/features/for-you/TasteProfile.tsx`**

```tsx
import type { TasteProfile as Profile } from "@/types/models";
import { GlassCard } from "@/design/GlassCard";
import { genreColor } from "@/lib/genres";

export function TasteProfile({ profile }: { profile: Profile | null }) {
  if (!profile || !profile.top_genres.length) return null;
  return (
    <GlassCard tone="warm" className="p-6 mb-8">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-2xl">Your taste</h2>
        <div className="text-sm text-text-muted tabular-nums">
          {profile.rating_count} ratings
          {profile.avg_score !== null
            ? ` · avg ${profile.avg_score.toFixed(1)}/10`
            : ""}
        </div>
      </div>
      <div className="space-y-2">
        {profile.top_genres.slice(0, 8).map((g) => {
          const w = Math.max(6, Math.round(g.weight * 100));
          const c = genreColor(g.genre);
          return (
            <div key={g.genre} className="flex items-center gap-3 text-sm">
              <div className="w-32 shrink-0 text-text-muted">{g.genre}</div>
              <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${w}%`, background: c }}
                />
              </div>
              <div className="w-10 text-right font-mono text-text-muted tabular-nums">
                {Math.round(g.weight * 100)}%
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/for-you/ForYouPage.tsx`**

```tsx
import { AnimeGrid } from "@/features/discover/AnimeGrid";
import { GlassCard } from "@/design/GlassCard";
import { useAuth } from "@/stores/auth";
import { useRecommendations } from "@/hooks/useRecommendations";
import { TasteProfile } from "./TasteProfile";

export function ForYouPage() {
  const user = useAuth((s) => s.user);
  const recs = useRecommendations(!!user);

  if (!user) {
    return (
      <div className="py-20 text-center">
        <h1 className="font-display text-4xl mb-2">Sign in to see your picks</h1>
        <p className="text-text-muted">
          Rate a few anime and your personal recommendations appear here.
        </p>
      </div>
    );
  }

  const items = (recs.data?.recommendations ?? []).map((r) => r.anime);

  return (
    <div>
      <h1 className="font-display text-4xl text-amber mb-6">For you</h1>
      <TasteProfile profile={recs.data?.taste_profile ?? null} />
      {recs.data?.recommendations?.length ? (
        <section>
          <h2 className="font-display text-2xl mb-4">Picks for tonight</h2>
          <AnimeGrid anime={items} loading={recs.isLoading} />
          <div className="mt-6 grid md:grid-cols-2 gap-4">
            {(recs.data?.recommendations ?? []).slice(0, 6).map((r) => (
              <GlassCard key={r.anime.id} className="p-4">
                <div className="font-semibold mb-1">
                  {r.anime.title_english ?? r.anime.title}
                </div>
                <p className="text-sm text-text-muted">{r.reason}</p>
              </GlassCard>
            ))}
          </div>
        </section>
      ) : (
        <AnimeGrid
          anime={[]}
          loading={recs.isLoading}
          empty="Rate a few anime to get personalized picks."
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire into router**

In `frontend/src/routes.tsx`, add import and replace for-you placeholder:

```tsx
import { ForYouPage } from "@/features/for-you/ForYouPage";
```

Replace `{ path: "for-you", element: <Placeholder name="For you" /> }` with:

```tsx
      { path: "for-you", element: <ForYouPage /> },
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useRecommendations.ts frontend/src/features/for-you/TasteProfile.tsx frontend/src/features/for-you/ForYouPage.tsx frontend/src/routes.tsx
git commit -m "Add for-you page with taste profile and recommendation reasons"
```

---

## Task 18: Chat page (3 modes: recommend, rate, onboard)

**Files:**
- Create: `frontend/src/hooks/useChat.ts`
- Create: `frontend/src/features/chat/ChatAnimeCard.tsx`
- Create: `frontend/src/features/chat/ChatPage.tsx`
- Modify: `frontend/src/routes.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useChat.ts`**

```ts
import { useState } from "react";
import { api } from "@/lib/api";
import type {
  ChatAnimeRef,
  ChatMessage,
  ChatRole,
} from "@/types/models";

type Mode = "recommend" | "rate" | "onboard";

interface TurnExtra {
  anime?: ChatAnimeRef[];
}

interface Turn {
  role: ChatRole;
  content: string;
  extra?: TurnExtra;
}

export function useChat(mode: Mode, seed: Turn[] = []) {
  const [turns, setTurns] = useState<Turn[]>(seed);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(userText: string) {
    if (!userText.trim()) return;
    const next: Turn[] = [...turns, { role: "user", content: userText }];
    setTurns(next);
    setLoading(true);
    setError(null);
    try {
      const conversation: ChatMessage[] = next.map((t) => ({
        role: t.role,
        content: t.content,
      }));
      const res = await api.chatMessage({
        message: userText,
        conversation,
        mode,
      });
      setTurns((curr) => [
        ...curr,
        {
          role: "assistant",
          content: res.response,
          extra: res.suggested_anime ? { anime: res.suggested_anime } : undefined,
        },
      ]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return { turns, setTurns, send, loading, error };
}

export type { Turn };
```

- [ ] **Step 2: Create `frontend/src/features/chat/ChatAnimeCard.tsx`**

```tsx
import { Link } from "react-router-dom";
import type { ChatAnimeRef } from "@/types/models";
import { Badge } from "@/design/Badge";
import { genreColor } from "@/lib/genres";

export function ChatAnimeCard({ anime }: { anime: ChatAnimeRef }) {
  const inner = (
    <div className="flex gap-3 p-3 rounded-lg border border-border bg-surface hover:border-border-strong transition-colors">
      {anime.image_url ? (
        <img
          src={anime.image_url}
          alt=""
          className="w-12 h-16 object-cover rounded"
        />
      ) : (
        <div className="w-12 h-16 rounded bg-white/5" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold truncate">{anime.title}</div>
        {anime.genres?.length ? (
          <div className="flex gap-1 flex-wrap mt-1.5">
            {anime.genres.slice(0, 3).map((g) => (
              <Badge key={g} color={genreColor(g)}>
                {g}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
  return anime.id ? (
    <Link to={`/anime/${anime.id}`} className="block">
      {inner}
    </Link>
  ) : (
    inner
  );
}
```

- [ ] **Step 3: Create `frontend/src/features/chat/ChatPage.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Button } from "@/design/Button";
import { GlassCard } from "@/design/GlassCard";
import { Input } from "@/design/Input";
import { cn } from "@/lib/cn";
import { useChat } from "@/hooks/useChat";
import type { Turn } from "@/hooks/useChat";
import { ChatAnimeCard } from "./ChatAnimeCard";

type Mode = "recommend" | "rate" | "onboard";

const SEED: Record<Mode, Turn[]> = {
  recommend: [
    {
      role: "assistant",
      content:
        "Hey — I'm your anime guide. Tell me what you're in the mood for and I'll pick three.",
    },
  ],
  rate: [],
  onboard: [
    {
      role: "assistant",
      content:
        "Let's build your taste profile. Name three anime you already love and a couple you disliked.",
    },
  ],
};

export function ChatPage() {
  const [params] = useSearchParams();
  const initialMode = (params.get("mode") as Mode) || "recommend";
  const [mode, setMode] = useState<Mode>(initialMode);
  const { turns, send, loading, error } = useChat(mode, SEED[mode]);
  const [input, setInput] = useState("");
  const scroller = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scroller.current?.scrollTo({
      top: scroller.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.length]);

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center gap-2 mb-4">
        <h1 className="font-display text-4xl text-amber">Guide</h1>
        <div className="ml-auto flex gap-1">
          {(["recommend", "rate", "onboard"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm",
                mode === m
                  ? "bg-white/[0.08] text-text"
                  : "text-text-muted hover:text-text"
              )}
            >
              {m === "recommend" ? "Recommend" : m === "rate" ? "Rate with AI" : "Onboard"}
            </button>
          ))}
        </div>
      </div>
      <GlassCard className="h-[60vh] flex flex-col">
        <div ref={scroller} className="flex-1 overflow-y-auto p-5 space-y-4">
          {turns.map((t, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "max-w-[85%]",
                t.role === "user" ? "ml-auto" : "mr-auto"
              )}
            >
              <div
                className={cn(
                  "px-4 py-3 rounded-2xl text-sm leading-relaxed",
                  t.role === "user"
                    ? "bg-amber text-bg"
                    : "bg-white/[0.04] border border-border"
                )}
              >
                {t.content}
              </div>
              {t.extra?.anime?.length ? (
                <div className="mt-2 grid gap-2">
                  {t.extra.anime.slice(0, 3).map((a, j) => (
                    <ChatAnimeCard key={j} anime={a} />
                  ))}
                </div>
              ) : null}
            </motion.div>
          ))}
          {loading ? (
            <div className="mr-auto px-4 py-3 rounded-2xl bg-white/[0.04] border border-border text-sm text-text-muted">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse mr-1" />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse mr-1 [animation-delay:0.15s]" />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse [animation-delay:0.3s]" />
            </div>
          ) : null}
        </div>
        <form
          className="p-3 border-t border-border flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!loading) {
              send(input);
              setInput("");
            }
          }}
        >
          <Input
            className="flex-1"
            placeholder="Type a message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <Button type="submit" loading={loading} disabled={!input.trim()}>
            Send
          </Button>
        </form>
      </GlassCard>
      {error ? (
        <p className="mt-3 text-sm text-danger">{error}</p>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Wire into router**

In `frontend/src/routes.tsx`, add import and replace chat placeholder:

```tsx
import { ChatPage } from "@/features/chat/ChatPage";
```

Replace `{ path: "chat", element: <Placeholder name="Chat" /> }` with:

```tsx
      { path: "chat", element: <ChatPage /> },
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/features/chat/ChatAnimeCard.tsx frontend/src/features/chat/ChatPage.tsx frontend/src/routes.tsx
git commit -m "Add chat page with three modes and animated message flow"
```

---

## Task 19: Page transitions + AppShell outlet wrap

**Files:**
- Modify: `frontend/src/layout/AppShell.tsx`
- Create: `frontend/src/layout/PageTransition.tsx`

- [ ] **Step 1: Create `frontend/src/layout/PageTransition.tsx`**

```tsx
import { AnimatePresence, motion } from "framer-motion";
import { useLocation, useOutlet } from "react-router-dom";
import { transitions } from "@/design/motion";

export function PageTransition() {
  const location = useLocation();
  const outlet = useOutlet();
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={transitions.ease}
      >
        {outlet}
      </motion.div>
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Update `frontend/src/layout/AppShell.tsx`**

Replace the contents of `AppShell.tsx` with:

```tsx
import { AmbientBlobs } from "@/design/AmbientBlobs";
import { GrainOverlay } from "@/design/GrainOverlay";
import { Header } from "./Header";
import { PageTransition } from "./PageTransition";

export default function AppShell() {
  return (
    <div className="relative min-h-screen bg-bg text-text">
      <AmbientBlobs />
      <GrainOverlay />
      <div className="relative z-10">
        <Header />
        <main className="max-w-7xl mx-auto px-6 py-10">
          <PageTransition />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/layout/AppShell.tsx frontend/src/layout/PageTransition.tsx
git commit -m "Add page transitions between routes"
```

---

## Task 20: Flask serves the new frontend build

**Files:**
- Modify: `app.py` (swap static_folder + SPA fallback)
- Modify: `build.sh` (build the frontend)
- Modify: `frontend/.env.example`
- Create: `frontend/e2e/smoke.spec.ts`
- Create: `frontend/playwright.config.ts`

- [ ] **Step 1: Update `app.py` to serve `frontend/dist/` with SPA fallback**

Open `app.py`. Find the `create_app()` function (around line 10-60). Replace the Flask instantiation and any existing static/index route with this block (leave the blueprint registration block intact):

```python
import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from models import db
from config import Config

# Serve the new Vite-built frontend from frontend/dist/. If that directory is
# missing (dev before build or CI stage 1) fall back to the legacy static/
# bundle so the server still returns usable HTML.
def _static_root() -> str:
    frontend = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if os.path.isdir(frontend) and os.path.exists(os.path.join(frontend, "index.html")):
        return frontend
    return os.path.join(os.path.dirname(__file__), "static")


def create_app() -> Flask:
    root = _static_root()
    app = Flask(__name__, static_folder=root, static_url_path="")
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    JWTManager(app)
    Bcrypt(app)
    db.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.anime import anime_bp
    from routes.ratings import ratings_bp
    from routes.anilist import anilist_bp
    from routes.chatbot import chatbot_bp
    from routes.recommend import recommend_bp
    from routes.watchlist import watchlist_bp
    from routes.search import search_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(anime_bp)
    app.register_blueprint(ratings_bp)
    app.register_blueprint(anilist_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(search_bp)

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def spa(path: str):
        # API routes are handled above; anything else serves the SPA index.
        full = os.path.join(app.static_folder, path)
        if path and os.path.exists(full) and os.path.isfile(full):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    with app.app_context():
        db.create_all()
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

If your existing `app.py` already wires blueprints identically, only replace the parts that changed — keep your own imports, env loading, and any custom middleware. The key additions are: `_static_root()`, `static_folder=root, static_url_path=""`, and the `spa()` catch-all route.

- [ ] **Step 2: Update `build.sh`**

Replace the contents of `build.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
pip install -r requirements.txt

pushd frontend > /dev/null
npm ci
npm run build
popd > /dev/null

python seed.py || true
```

- [ ] **Step 3: Create `frontend/.env.example`**

```
VITE_API_URL=http://localhost:5000/api
```

- [ ] **Step 4: Create `frontend/playwright.config.ts`**

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev",
    port: 5173,
    reuseExistingServer: !process.env.CI,
  },
});
```

- [ ] **Step 5: Create `frontend/e2e/smoke.spec.ts`**

```ts
import { test, expect } from "@playwright/test";

test("landing renders hero and nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Discover what/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Discover" })).toBeVisible();
});

test("discover loads grid", async ({ page }) => {
  await page.goto("/discover");
  await expect(page.getByRole("heading", { name: "Discover" })).toBeVisible();
});

test("404 path navigates to landing", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
});
```

- [ ] **Step 6: Smoke-test the full stack**

From the project root:

```bash
cd frontend && npm run build
cd ..
python -m flask --app app run --port 5000 &
sleep 4
curl -sI http://127.0.0.1:5000/ | head -1
curl -s http://127.0.0.1:5000/ | grep -q "root" && echo "SPA served"
curl -s http://127.0.0.1:5000/api/health | grep -q "ok" && echo "API ok"
kill %1 2>/dev/null || true
```

Expected: `HTTP/1.1 200 OK`, `SPA served`, `API ok`.

- [ ] **Step 7: Run Vitest full suite**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass.

- [ ] **Step 8: Run Playwright smoke**

```bash
cd frontend && npx playwright install --with-deps chromium
cd frontend && npx playwright test
```

Expected: 3 passing.

- [ ] **Step 9: Commit**

```bash
git add app.py build.sh frontend/.env.example frontend/playwright.config.ts frontend/e2e/smoke.spec.ts
git commit -m "Serve built frontend from Flask with SPA fallback and wire Playwright smoke"
```

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-04-17-bingery-revamp-design.md`):

| Spec section | Covered in |
|---|---|
| Vite + React + TS + Tailwind | Task 1, 2 |
| Design tokens (bg, amber, violet, fonts) | Task 2 |
| Ambient blobs (2, soft) + grain 14% | Task 8 |
| LiquidGL hero surfaces | Task 9, used in 11, 15 |
| React Router v6 | Task 5 |
| TanStack Query + Zustand | Task 4 |
| API client with auth | Task 3 |
| Framer Motion (buttons, transitions) | Tasks 6, 19 |
| Landing page | Task 11 |
| Auth (login + register) | Task 12 |
| Discover + filters + search | Tasks 13, 14 |
| Detail (hero, rating, fan genres, similar) | Task 15 |
| Watchlist (status tabs, favorites) | Task 16 |
| For-you + taste profile | Task 17 |
| Chat (3 modes) | Task 18 |
| Page transitions | Task 19 |
| Flask serves build + SPA fallback | Task 20 |
| Legacy static/index.html preserved | Not touched — Plan 3 archives |

New feature UIs (Collections, Stats, Seasonal, Activity, Compare) are deferred to Plan 3 by design; their backend endpoints land in Plan 1.

**2. Placeholder scan**: No TBD/TODO/"fill in" strings. Every step has concrete code.

**3. Type consistency**:
- `WatchStatus` union: `watching|completed|plan_to_watch|on_hold|dropped` — used consistently across `models.ts`, `StatusTabs.tsx`, `useWatchlist.ts`.
- `api.setWatchStatus` takes `{ status: string }` to match Flask accepting any status string; types are validated on server.
- `AnimeDetail.user_rating` shape is `{ score, review } | null` — matches `RatingPanel` usage.
- `TasteProfile.top_genres` is `Array<{ genre; weight }>` — matches `TasteProfile.tsx`.
- `ChatResponse.suggested_anime?` optional — handled in `useChat` with `res.suggested_anime ?` guard.

**4. Scope check**: 20 tasks, producing a self-contained working frontend at the end. Plan is executable independently of Plan 3. Plan 1's new backend endpoints (Collections, Stats, Activity, Seasonal, Compare) are not consumed here — their UIs are Plan 3.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-plan-2-frontend-foundation.md`.

Two execution options (same as Plan 1):

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — tasks executed in this session.

Plan 3 (new feature UIs + polish + deploy) is next. I recommend writing Plan 3 before execution begins so you can see the full arc.
