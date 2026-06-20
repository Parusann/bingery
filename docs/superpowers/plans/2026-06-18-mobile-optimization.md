# Mobile Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A mobile polish pass (tap targets, density, dense widgets, fluid type, detail/rating UX) plus making Bingery an installable PWA.

**Architecture:** Mostly Tailwind/CSS class changes across a handful of components, one responsive rework of `StarRating`, a `.text-display` clamp utility in `index.css`, and `vite-plugin-pwa` for the manifest + service worker + generated icons.

**Tech Stack:** React + TypeScript + Vite + Tailwind; vitest + RTL; `vite-plugin-pwa` (Workbox).

Spec: `docs/superpowers/specs/2026-06-18-mobile-optimization-design.md`
Branch: `feat/mobile-optimization`

**Conventions:** mobile-first (base = phone, `sm:`+ restores desktop). 44px tap-target floor. Commit messages contain NO AI/Claude attribution. Run frontend commands from `frontend/`. Verify each task with `npm run build` (tsc + vite). When editing, the native Read may be truncated by a context hook — get exact content via Grep (`^`) or desktop-commander `read_file` first.

---

## Task 1: Tap targets ≥44px (FilterBar, NavBar)

**Files:** `frontend/src/features/discover/FilterBar.tsx`, `frontend/src/layout/NavBar.tsx`

- [ ] **Step 1: Edit FilterBar controls**
  - Genre chips (the `~px-3 py-1.5 text-xs` pill button): change to `px-3.5 py-2 text-sm min-h-[44px] inline-flex items-center` (keep existing color/active classes).
  - Sort buttons (the `~px-2 py-1` button): change to `px-3 py-2 text-sm min-h-[44px] inline-flex items-center`.
- [ ] **Step 2: Edit NavBar links**
  - The desktop nav `<NavLink>`/`<a>` (`~px-3 py-1.5`): change to `px-3 py-2.5 min-h-[44px] inline-flex items-center` (desktop nav, but harmless to size up).
- [ ] **Step 3:** Run `npm run build` → clean.
- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/features/discover/FilterBar.tsx frontend/src/layout/NavBar.tsx
  git commit -m "fix(mobile): enlarge filter/sort/nav tap targets to >=44px"
  ```

(Gather the exact current className strings for each control first, then apply the minimal change preserving all other classes.)

---

## Task 2: Fluid display headings

**Files:** `frontend/src/index.css`, `frontend/src/features/discover/DiscoverPage.tsx`, `frontend/src/features/watchlist/WatchlistPage.tsx`, `frontend/src/features/details/DetailHero.tsx`

- [ ] **Step 1: Add clamp utilities** to the `@layer utilities` block in `frontend/src/index.css` (after `.ring-amber`):
  ```css
  .text-display {
    font-size: clamp(1.6rem, 5.5vw, 2.25rem);
    line-height: 1.1;
  }
  .text-display-hero {
    font-size: clamp(1.9rem, 7vw, 3rem);
    line-height: 1.05;
  }
  ```
- [ ] **Step 2: Apply to page h1s.** In `DiscoverPage.tsx` and `WatchlistPage.tsx`, the page `<h1 className="font-display text-4xl ...">` → replace `text-4xl` with `text-display`. In `DetailHero.tsx:35` the title `text-4xl md:text-5xl` → `text-display-hero` (drop the `text-4xl md:text-5xl`).
- [ ] **Step 3:** Run `npm run build` → clean.
- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/index.css frontend/src/features/discover/DiscoverPage.tsx frontend/src/features/watchlist/WatchlistPage.tsx frontend/src/features/details/DetailHero.tsx
  git commit -m "fix(mobile): fluid clamp() display headings so h1s fit small phones"
  ```

---

## Task 3: Tighter 2-col cards on phones

**Files:** `frontend/src/features/discover/AnimeCard.tsx`

- [ ] **Step 1: Reduce density at the base breakpoint** (restore at `sm:`):
  - Card body padding `p-3` → `p-2 sm:p-3`.
  - Title (`line-clamp-2 text-sm ...`) → `line-clamp-2 text-xs sm:text-sm ...`.
  - Genre badges: show fewer below `sm`. The badges currently `.slice(0, 3)` (or similar) — wrap the 2nd/3rd badge in a `hidden sm:inline-flex` wrapper, or slice to `isSmall ? 1 : 3`. Simplest CSS-only: keep up to 3 in markup but add `hidden sm:flex` to the badge row's extra items — i.e. show 1 badge below sm, up to 3 at sm+. (Confirm exact current badge markup, then apply.)
- [ ] **Step 2:** Run `npm run build` → clean.
- [ ] **Step 3: Commit**
  ```bash
  git add frontend/src/features/discover/AnimeCard.tsx
  git commit -m "fix(mobile): tighten 2-col card padding/badges/title on phones"
  ```

(`WatchlistCard` large variant already received compact treatment in the watchlist PR; leave it. This task is the Discover card.)

---

## Task 4: Dense widgets (heatmap, chat)

**Files:** `frontend/src/features/stats/ActivityHeatmap.tsx`, `frontend/src/features/chat/ChatPage.tsx`

- [ ] **Step 1: ActivityHeatmap scroll affordance.** Wrap the existing `overflow-x-auto` grid (`:39`) in a `relative` container and add a right-edge fade overlay + `scroll-snap-type: x proximity` on the scroller. Concretely, on the scroller add classes `snap-x [scrollbar-width:thin]` and on each week column add `snap-start`; add a sibling fade: `<div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-bg to-transparent sm:hidden" />`.
- [ ] **Step 2: ChatPage height.** Replace the fixed scroller height `h-[60vh] md:h-[68vh]` with a flex-fill approach: make the chat container a `flex min-h-0 flex-col` that fills its parent, and the message list `flex-1 min-h-0 overflow-y-auto` (so the composer stays visible and it doesn't fight the `pb-24` tab-bar reservation). If the page root needs a height anchor, use `min-h-[calc(100dvh-…)]`/`flex-1` on the page wrapper rather than a raw `vh` on the scroller. (Read the current ChatPage structure and apply the minimal change to remove the raw `vh`.)
- [ ] **Step 3:** Run `npm run build` → clean.
- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/features/stats/ActivityHeatmap.tsx frontend/src/features/chat/ChatPage.tsx
  git commit -m "fix(mobile): heatmap scroll affordance + chat height that respects the tab bar"
  ```

---

## Task 5: Rating UI — responsive StarRating + chips (TDD)

**Files:** `frontend/src/design/StarRating.tsx`, `frontend/src/features/details/RatingPanel.tsx`, test `frontend/src/design/StarRating.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/design/StarRating.test.tsx`:
  ```tsx
  import { describe, it, expect, vi } from "vitest";
  import { render, screen } from "@testing-library/react";
  import userEvent from "@testing-library/user-event";
  import { StarRating } from "./StarRating";

  describe("StarRating", () => {
    it("renders 10 rating buttons", () => {
      render(<StarRating value={0} onChange={() => {}} />);
      expect(screen.getAllByRole("button")).toHaveLength(10);
    });

    it("reports the clicked star's value", async () => {
      const onChange = vi.fn();
      render(<StarRating value={0} onChange={onChange} />);
      await userEvent.click(screen.getByLabelText("Rate 7 of 10"));
      expect(onChange).toHaveBeenCalledWith(7);
    });
  });
  ```
  Run `npx vitest run src/design/StarRating.test.tsx` → it should PASS already (behavior is unchanged) — this is a guard so the responsive refactor in Step 2 can't break the interaction. If the frontend has no RTL/jsdom env configured, add `// @vitest-environment jsdom` as the first line of the test file. (Existing frontend tests already use RTL, so the env is configured.)
- [ ] **Step 2: Make StarRating responsive** — replace the component body so the row is full-width with `flex-1` touch zones on mobile and reverts to inline at `sm:`. New `StarRating.tsx`:
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

  export function StarRating({ value, onChange, readOnly, size = 24, className }: Props) {
    const [hover, setHover] = useState(0);
    const display = hover || value;
    return (
      <div className={cn("w-full sm:w-auto", className)}>
        <div
          className="flex w-full items-center sm:inline-flex sm:w-auto sm:gap-0.5"
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
                  "flex flex-1 items-center justify-center py-2 transition-transform sm:flex-none sm:p-0.5",
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
          <span className="ml-2 hidden text-sm text-text-muted tabular-nums sm:inline">
            {display}/10
          </span>
        </div>
        <div className="mt-1 text-center text-sm text-text-muted tabular-nums sm:hidden">
          {display}/10
        </div>
      </div>
    );
  }
  ```
- [ ] **Step 3: RatingPanel fan-genre chips** — the vote chip button (`px-3 py-1 rounded-full text-xs ...`) → `px-3.5 py-2 rounded-full text-sm min-h-[44px] inline-flex items-center ...` (keep the active/color classes); the wrapping row `gap-1.5` → `gap-2`.
- [ ] **Step 4:** Run `npx vitest run src/design/StarRating.test.tsx` → PASS, then `npm run build` → clean.
- [ ] **Step 5: Commit**
  ```bash
  git add frontend/src/design/StarRating.tsx frontend/src/design/StarRating.test.tsx frontend/src/features/details/RatingPanel.tsx
  git commit -m "fix(mobile): touch-friendly star rating + larger fan-genre chips"
  ```

---

## Task 6: Detail page padding

**Files:** `frontend/src/features/details/AnimeDetailPage.tsx`, `frontend/src/features/details/DetailHero.tsx`

- [ ] **Step 1:** In `AnimeDetailPage.tsx`, the two detail section cards `<GlassCard className="p-6">` and `<GlassCard tone="warm" className="p-6">` → `p-4 sm:p-6`.
- [ ] **Step 2:** In `DetailHero.tsx:26`, the `LiquidGLSurface` `p-6 md:p-10` → `p-4 sm:p-6 md:p-10` (less crowding on phones). (Hero title already handled in Task 2.)
- [ ] **Step 3:** Run `npm run build` → clean.
- [ ] **Step 4: Commit**
  ```bash
  git add frontend/src/features/details/AnimeDetailPage.tsx frontend/src/features/details/DetailHero.tsx
  git commit -m "fix(mobile): tighten detail hero + section padding on phones"
  ```

---

## Task 7: PWA (installable + app-shell cache)

**Files:** `frontend/package.json` (dep), `frontend/vite.config.ts`, `frontend/public/icon-192.png`, `frontend/public/icon-512.png`, `frontend/public/icon-maskable-512.png`

- [ ] **Step 1: Install the plugin** (from `frontend/`): `npm install -D vite-plugin-pwa`
- [ ] **Step 2: Generate icons.** Create the three PNGs (dark `#080510` background, amber `#e6a680` "B" monogram) with a one-off script. Prefer Python Pillow:
  ```python
  # scripts/gen_pwa_icons.py  (run once: python scripts/gen_pwa_icons.py)
  from PIL import Image, ImageDraw, ImageFont
  import os
  OUT = os.path.join("frontend", "public")
  def make(size, pad, name):
      img = Image.new("RGBA", (size, size), (8, 5, 16, 255))
      d = ImageDraw.Draw(img)
      try:
          font = ImageFont.truetype("arial.ttf", int(size * 0.6))
      except Exception:
          font = ImageFont.load_default()
      t = "B"
      box = d.textbbox((0, 0), t, font=font)
      w, h = box[2] - box[0], box[3] - box[1]
      d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), t, fill=(230, 166, 128, 255), font=font)
      img.save(os.path.join(OUT, name))
  make(192, 0, "icon-192.png")
  make(512, 0, "icon-512.png")
  make(512, 64, "icon-maskable-512.png")
  print("icons written")
  ```
  If Pillow is missing: `pip install Pillow` then run it. (The script is a one-off generator; it does not ship.)
- [ ] **Step 3: Configure vite-plugin-pwa** in `frontend/vite.config.ts` — add the import and the plugin (manifest auto-linked; SW auto-registered):
  ```ts
  import { defineConfig } from "vite";
  import react from "@vitejs/plugin-react";
  import { VitePWA } from "vite-plugin-pwa";
  import path from "node:path";

  export default defineConfig({
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        includeAssets: ["grain.svg"],
        manifest: {
          name: "Bingery — Anime Discovery",
          short_name: "Bingery",
          description: "Discover, track, and rate anime.",
          theme_color: "#080510",
          background_color: "#080510",
          display: "standalone",
          start_url: "/",
          icons: [
            { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
            { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
            { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          ],
        },
        workbox: {
          globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
          navigateFallbackDenylist: [/^\/api/],
        },
      }),
    ],
    resolve: { alias: { "@": path.resolve(__dirname, "src") } },
    server: {
      port: 5173,
      proxy: { "/api": { target: "http://127.0.0.1:5000", changeOrigin: true } },
    },
    build: { outDir: "dist", sourcemap: false },
  });
  ```
  `navigateFallbackDenylist` keeps the SW from hijacking `/api` calls; `autoUpdate` avoids a stale SW pinning old assets.
- [ ] **Step 4: Build and confirm PWA output** (from `frontend/`): `npm run build`, then verify the artifacts exist:
  `ls dist/manifest.webmanifest dist/sw.js dist/icon-192.png` (or `dist/registerSW.js` — vite-plugin-pwa emits `sw.js` + the manifest).
  Expected: build clean; `manifest.webmanifest` + a service worker + the icons present in `dist/`.
- [ ] **Step 5: Commit**
  ```bash
  git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/public/icon-192.png frontend/public/icon-512.png frontend/public/icon-maskable-512.png scripts/gen_pwa_icons.py
  git commit -m "feat(mobile): make Bingery an installable PWA (manifest + service worker + icons)"
  ```

---

## Task 8: Full verification

**Files:** none

- [ ] **Step 1: Frontend tests + build** (from `frontend/`): `npm run test:run` (all pass incl. the new StarRating test) and `npm run build` (clean; PWA artifacts emitted).
- [ ] **Step 2: Manual responsive smoke** at ~360px (devtools device toolbar or a phone): filter/sort/nav taps feel ≥44px; Discover cards breathe in 2-col; ActivityHeatmap shows a scroll fade; ChatPage message area + composer both usable above the tab bar; anime detail title fits; star rating is easy to tap and the `/10` shows below; fan-genre chips are tappable; "Add to Home Screen" appears and the installed app opens full-screen.
- [ ] **Step 3:** If green, no extra commit. Otherwise fix + commit with a descriptive message.

---

## Self-review

- **Spec coverage:** tap targets (Task 1) ✓; fluid headings (Task 2) ✓; tighter cards (Task 3) ✓; dense widgets heatmap+chat (Task 4) ✓; rating UI — responsive stars + chips (Task 5) ✓; detail padding (Task 6) ✓; PWA install+shell (Task 7) ✓; StarRating test + build/manifest verification (Tasks 5, 7, 8) ✓.
- **No placeholders:** new/substantial code (clamp utilities, full responsive `StarRating`, StarRating test, vite-plugin-pwa config, icon generator) is given in full. Component tweaks are specified as exact before→after class changes; each task says to read the current exact className first (the context hook truncates blind reads) and apply the minimal change preserving other classes.
- **Name/consistency:** `.text-display` / `.text-display-hero` defined in Task 2 and applied in Tasks 2 & 6; `StarRating` API unchanged (`value`, `onChange`, `readOnly`, `size`, `className`) so its single caller `RatingPanel` is unaffected beyond the chip change; PWA manifest icon paths match the generated files.
- **Out of scope (per spec):** custom install UI, offline write/sync, tablet layouts, restyle — none added.
- **Risk note:** Task 7's service worker is the riskiest; `autoUpdate` + `/api` denylist mitigate stale-cache and API-hijack issues; verify on iOS Safari in smoke.
