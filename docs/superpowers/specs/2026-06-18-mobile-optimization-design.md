# Mobile Optimization — Design

Date: 2026-06-18
Status: Approved (pending spec review)
Branch: `feat/mobile-optimization`

## Problem

From the fix list:

> Format on mobile can still be better optimized (this might be even better
> improved with an actual app).

Plus a specific ask from the product owner: make a serious effort on the
**anime detail page and the rating UI** on mobile.

The navigation architecture is already solid (a `md:hidden` `MobileHeader` + a
fixed `BottomTabBar` with a `MoreSheet`, and `Modal` docks to a bottom sheet via
the one `useIsDesktop` use). The gaps are in control sizing, density, a couple of
desktop-shaped widgets, the rating flow, and the lack of installability.

## Goals

1. Comfortable, correctly-sized touch controls and density on phones.
2. A serious mobile pass on the anime detail + rating experience.
3. Make Bingery installable (PWA): home-screen icon, full-screen launch, cached
   app shell.

## Decisions (confirmed with product owner)

- **PWA included** this round (install + offline app-shell). No App Store / native build.
- **Star rating on mobile:** responsive enlargement (stars become full-width touch
  zones), not a slider swap.
- **Tap-target floor:** 44px (Apple HIG).
- **Target device floor:** optimize for ~360–390px modern phones; 320px must still
  work without horizontal overflow (2-col stays 2-col, just tighter).
- **PWA icon:** generate a simple Bingery monogram (no logo asset exists; only
  `frontend/public/grain.svg`).

## Non-goals (YAGNI)

- Custom in-app "install" prompt UI (browsers provide their own).
- Offline write/sync (only the app shell + last-viewed is cached; mutations need network).
- Bespoke tablet/iPad layouts.
- A Tailwind/visual redesign — targeted fixes only.

## Current state (verified; file:line)

- Sub-44px controls: `FilterBar.tsx:25` genre chips `px-3 py-1.5` (~30px), `:59`
  sort buttons `px-2 py-1` (~28px); `NavBar.tsx:26` links `px-3 py-1.5`.
- Dense cards: `AnimeCard.tsx:69` `p-3` + `:70` 2-line title + `:73-79` up to 3
  badges, inside `AnimeGrid.tsx:33` `grid-cols-2 ...`; same grid in
  `WatchlistPage.tsx`.
- Dense widgets: `ActivityHeatmap.tsx:39` `flex gap-0.5 overflow-x-auto` + `:45`
  `w-2.5` cells (silent horizontal scroll); `ChatPage.tsx:~102` `h-[60vh] md:h-[68vh]`
  inside a page that reserves `pb-24` for the fixed tab bar (`AppShell.tsx:21`).
- Type: `index.css` single `font-size:15px`, no fluid scaling; big `text-4xl` h1s
  on Discover/Watchlist and `DetailHero.tsx:35` `text-4xl md:text-5xl` title.
- Rating UI: `StarRating.tsx` 10 buttons each `p-0.5` around a 20px svg (~24px tap
  target), `gap-0.5`; readout inline. Used in exactly one place — `RatingPanel.tsx:41`
  (interactive, never `readOnly`). `RatingPanel.tsx:69` fan-genre chips `px-3 py-1`
  (~28px). Detail sections wrap content in `GlassCard ... p-6` (`AnimeDetailPage.tsx:56,69`).
- No PWA: `vite.config.ts` has only `react()`; `index.html` has viewport +
  theme-color but no manifest/service worker.

## Approach & components

### 1. Global controls & fluid type
- Raise to ≥44px: `FilterBar` genre chips + sort buttons; `NavBar` links. (Keep
  existing labels; grow padding / min-height.)
- Add a `.text-display` utility in `index.css` using `clamp()` and apply it to the
  big h1s (Discover, Watchlist) and the detail hero title so they scale down on
  small phones instead of forcing line wraps / eating vertical space.

### 2. Dense screens (cards)
- `AnimeCard` (and `WatchlistCard` large variant): at the base/2-col breakpoint
  reduce padding `p-3`→`p-2 sm:p-3`, cap visible genre badges to ~2 below `sm`,
  and slightly smaller title; restore current sizing at `sm:`+. No grid-column
  change (2-col floor stays; just breathing room).

### 3. Dense widgets
- `ActivityHeatmap`: keep the horizontal scroll but make it legible — add a
  right-edge fade + `scroll-snap` so it's clear the grid scrolls rather than
  silently clipping.
- `ChatPage`: replace the fixed `h-[60vh]` scroller with a flex column that fills
  available height (use `min-h-0` + `flex-1`, and `100dvh`-aware sizing) so the
  message area and composer don't fight the fixed bottom tab bar on short phones.

### 4. Detail + rating mobile pass
- `StarRating`: make it responsive **without changing desktop**. On mobile (base):
  the 10 star buttons each become `flex-1` across a full-width row with taller
  padding (≈33px wide × ≈40px tall touch zones, up from ~24px), and the `/10`
  readout moves to its own line. At `sm:`+: revert to the current inline `gap-0.5`
  auto-width layout with the inline readout. Larger star glyph on mobile. (The
  `readOnly` path is unused today, but keep it inline regardless.)
- `RatingPanel`: fan-genre vote chips → ≥44px tap height with comfortable spacing;
  ensure the Save button row is thumb-reachable.
- `DetailHero`: apply the fluid title; tighten hero padding on phones (`p-6`
  already mobile, verify poster + stats don't crowd; stats stay `grid-cols-2`).
- Detail section cards: `GlassCard` `p-6`→`p-4 sm:p-6` so the rating/genre panels
  aren't over-padded on small screens.

### 5. PWA
- Add `vite-plugin-pwa` to `vite.config.ts` with `registerType: "autoUpdate"`, a
  manifest (name "Bingery", short_name, `display: standalone`, theme/background
  colors matching the existing dark theme + `theme-color` meta, start_url "/"),
  and Workbox precaching of the built app shell. Generate `192x192` + `512x512`
  (incl. a maskable) PNG icons (a simple Bingery monogram) into `frontend/public`,
  referenced by the manifest. Link the manifest from `index.html`. No custom
  install UI.

## Testing

- `npm run build` succeeds and emits the manifest + a service worker into `dist/`
  (PWA wiring works).
- A light `StarRating` test (vitest + RTL): renders 10 rating buttons and clicking
  one calls `onChange` with that value (behavior unchanged by the responsive
  styling).
- Full frontend suite stays green (`npm run test:run`).
- Manual responsive smoke at ~360px: tap targets feel right; cards breathe;
  heatmap scroll is obvious; chat doesn't fight the tab bar; detail/rating is
  comfortable; "Add to Home Screen" appears and the installed app launches
  full-screen.

## Rollout / risk

- Mostly CSS/Tailwind class changes — low risk, reversible, no API/schema impact.
- Largest new surface is the PWA service worker: scope it to precache the app
  shell with `autoUpdate` so a stale SW can't pin old assets; verify on iOS Safari
  (its PWA support has known quirks) during smoke. The SW only activates in the
  built app, so dev is unaffected.
