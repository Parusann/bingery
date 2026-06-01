# Mobile Optimization — Design Spec

**Date:** 2026-06-01
**Status:** Approved design, ready for implementation planning
**App:** Bingery (anime tracker) — https://bingery.fly.dev

---

## 1. What this document is

This is a design spec for making the Bingery frontend a **full, native-feeling mobile app below 768px** while keeping the desktop experience (≥768px) **pixel-identical to what ships today**.

It has two audiences:

1. **The implementation plan** (`docs/superpowers/plans/…`) and whoever executes it in this repo.
2. **Claude design** (claude.ai) — used to mock up and generate the new mobile components. It cannot see this repo, so Sections 4–9 embed everything it needs: the exact design tokens, conventions, primitives, and per-component specs. **Section 4 is the output-format contract** — read it first if you are generating code.

---

## 2. Goal and the one hard constraint

**Goal:** Every page of the app feels like a purpose-built mobile app on a phone — thumb-friendly navigation, no horizontal overflow, comfortable tap targets, layouts composed for a ~390px viewport.

**Hard constraint (load-bearing):** **At ≥768px the app must render exactly as it does now — same layout, same spacing, same type, byte-identical.** This is non-negotiable and shapes every technical decision below. "Desktop" = any viewport ≥768px (laptops, desktops, tablets in landscape). "Mobile" = anything <768px (all phones).

Why 768px: Tailwind's default `md` breakpoint is 768px and the app *already* uses `md:` as its desktop/mobile divider in many components. Aligning to it means desktop styles are preserved by construction (see Section 6).

---

## 3. Locked scope decisions

| Decision | Choice |
| --- | --- |
| **Ambition** | Full native-feel mobile app (bottom-tab nav, mobile header, sheets, touch-sized controls, bespoke mobile layouts where needed). |
| **Page scope** | Full app sweep — every feature page. |
| **Desktop preservation line** | ≥768px stays pixel-identical; all mobile work lives in the `<768px` (unprefixed base) range. |
| **Primary test target** | iPhone-class, ~390px wide (also sanity-check ~360px). |
| **Mobile navigation pattern** | Bottom tab bar with 4 primary tabs + a **More** tab that opens a sheet. |
| **Primary tabs** | Discover · Schedule · Watchlist · For you. |
| **More sheet holds** | Seasonal, Collections, Stats, Activity, Compare, Chat + account block (display name, Sign in/out) + the NSFW visibility toggle. |
| **Touch targets** | Surgical (44px min on small interactive elements on mobile). No global `Button` resize. |
| **Modals** | Bottom sheet `<768px`, centered dialog `≥768px`. |

---

## 4. Output format & conventions (the contract for generated code)

Generated code must drop into this repo unchanged. Follow these exactly.

**Stack**
- React 18 + TypeScript, built with Vite.
- Tailwind CSS with **default breakpoints** (`sm` 640, `md` 768, `lg` 1024, `xl` 1280). Do **not** add custom breakpoints.
- `framer-motion` for animation (already a dependency).
- `lucide-react` for icons (already a dependency).
- `react-router-dom` v6 (`NavLink`, `useNavigate`, `useLocation`, `useSearchParams`).
- `zustand` stores for global state.
- **No new npm dependencies. No backend changes.**

**Imports & helpers**
- Path alias `@/` → `frontend/src/`. Example: `import { GlassCard } from "@/design/GlassCard";`.
- Conditional classes use `cn()` from `@/lib/cn` (a `clsx`-style helper). Example: `cn("base", isActive && "text-amber")`.
- Global stores: `useAuth` from `@/stores/auth` (exposes `user`, `signOut`), `useNsfw` from `@/stores/nsfw` (exposes `visible`, `toggle`).

**Styling rules**
- **Tailwind utility classes only.** No CSS modules, no styled-components, no inline `style` except for dynamic values that can't be expressed as classes (e.g. `style={{ paddingBottom: "env(safe-area-inset-bottom)" }}` or framer-motion `style`).
- Use the project's **semantic token classes** (defined in `tailwind.config.ts`, mirrored in Section 5): `bg-bg`, `bg-bg-elevated`, `bg-surface`, `text-text`, `text-text-muted`, `text-text-dim`, `border-border`, `border-border-strong`, `text-amber`, `text-peach`, `text-gold`, `text-ink`, etc. Do not hardcode hex values in components.
- Fonts via classes only: `font-display` (serif headings), `font-sans` (default body — no class needed), `font-mono` (labels/numbers). Do not change font loading.

**Component conventions**
- One component per file, **named export**, PascalCase filename, functional component with a typed `Props`/local interface.
- Reuse existing primitives instead of re-rolling: `GlassCard`, `Button`, `Modal`, `Input`, `Skeleton`, `Badge` from `@/design/*` (APIs in Section 5).
- Match the existing motion vocabulary — import `transitions` and variants from `@/design/motion` (`transitions.spring`, `transitions.easeFast`, etc.) rather than inventing new durations.

**Mobile-first discipline (the preservation mechanic — see Section 6)**
- Unprefixed utilities = mobile (`<768px`). `md:` utilities = desktop.
- When changing an existing component's layout for mobile, **move the current value to a `md:` prefix and put the mobile value in the base.** Never edit or remove an existing `md:`/`lg:` utility, and never change desktop-only markup.

**Deliverable shape**
- New components: full file contents with their target path (Section 11 manifest).
- Edited components: the precise class-string / markup changes, expressed so desktop output is unchanged.

---

## 5. Design system reference (embedded for Claude design)

### Palette (dark theme; `color-scheme: dark`)

| Token (class) | Value | Use |
| --- | --- | --- |
| `bg` | `#080510` | App background (near-black violet) |
| `bg-elevated` | `#0f0a1a` | Elevated surfaces, sheets, modals |
| `surface` | `rgba(255,255,255,0.04)` | Card fills |
| `surface-strong` | `rgba(255,255,255,0.08)` | Hover fills |
| `border` | `rgba(255,255,255,0.08)` | Default borders |
| `border-strong` | `rgba(255,255,255,0.16)` | Emphasis borders |
| `amber` | `#e6a680` | **Primary accent** (active nav, CTAs, links) |
| `amber-soft` | `#d9b899` | Softer accent |
| `violet` | `#b89ac4` | Secondary accent |
| `text` | `rgba(255,255,255,0.92)` | Primary text |
| `text-muted` | `rgba(255,255,255,0.64)` | Secondary text |
| `text-dim` | `rgba(255,255,255,0.42)` | Tertiary / placeholders |
| `danger` | `#e78a8a` | Errors |
| `success` | `#8fc9a4` | Success |
| `peach` / `peach-hi` / `peach-deep` | `#f4b690` / `#ffd0ad` / `#d99368` | Schedule accents |
| `gold` / `gold-bd` | `#f4cf90` / `rgba(244,207,144,0.42)` | Watchlist highlight on schedule |
| `ink` / `ink-2` | `#f3ece4` / `#cbc1b6` | Schedule text |
| `mute` / `mute-2` | `#8a8090` / `#5a5263` | Schedule muted text |
| `line` / `line-2` | `rgba(243,236,228,0.08)` / `.14` | Schedule hairlines |
| `row-bg` / `row-bg-hover` / `row-bd` | white @ .025 / .05 / .06 | Schedule rows |

### Radii (class `rounded-*`)
`sm` 6px · `md` 10px · `lg` 16px · `xl` 22px · `pill` 9999px

### Fonts (visual intent for mockups)
- **Display** (`font-display`, headings `h1`–`h3`): elegant high-contrast serif — token stack `Instrument Serif`; the bundled webfont in this repo is **Fraunces**. Use a refined serif.
- **Body** (`font-sans`, default): clean grotesque sans — token stack `Geist`; bundled webfont **Inter**.
- **Mono** (`font-mono`, labels/counts/timestamps): `Geist Mono` / bundled **JetBrains Mono**. Used heavily for uppercase tracked micro-labels.
- Base body size 15px, line-height 1.55. Headings use `letter-spacing: -0.01em`.

### Motion (framer-motion, from `@/design/motion`)
- Easing: `ease [0.22,1,0.36,1]`, `easeOut [0.16,1,0.3,1]`.
- Durations: fast 0.18s · base 0.28s · slow 0.45s.
- Springs: `soft {stiffness 260, damping 28}`, `snappy {stiffness 420, damping 32}`.
- Exposed: `transitions.ease`, `transitions.easeFast`, `transitions.spring` (=soft), `transitions.springSnappy` (=snappy); variants `fadeInUp`, `fadeIn`, `scaleIn`.

### Shared primitives (APIs to reuse)
- **`GlassCard`** — `props: { tone?: "default" | "warm" | "cool"; elevated?: boolean; className?; ...divProps }`. Renders `rounded-xl border border-border glass-edge backdrop-blur-md` + tone gradient.
- **`Button`** — `props: { variant?: "primary" | "ghost" | "glass" | "danger"; size?: "sm" | "md" | "lg"; loading?; leading?; trailing?; ...buttonProps }`. Pill-shaped; sizes are `sm` h-8 (32px), `md` h-10 (40px), `lg` h-12 (48px); built-in press animation.
- **`Modal`** — `props: { open: boolean; onClose: () => void; maxWidth?: string; className?; children }`. Currently a centered, scale-in dialog with backdrop + Escape-to-close. **This component is modified in Section 8.**
- **`Input`** — `props: { label?; error?; leading?; ...inputProps }`. `h-10`, `rounded-lg`, surface fill, amber focus ring.
- **`Skeleton`**, **`Badge`**, **`StarRating`** — loading/label/rating primitives.
- `.glass-edge` utility = layered inset highlight + drop shadow (defined in `index.css`).

### Routes (all destinations)
`/discover` · `/seasonal` · `/schedule` · `/watchlist` · `/collections` (+`/collections/:id`) · `/for-you` · `/stats` · `/activity` · `/compare` · `/chat` · `/anime/:id` (detail) · `/auth` · `/` (landing) · `/admin/dub-reports`.

---

## 6. Breakpoint & preservation strategy

Tailwind is **mobile-first**: an unprefixed utility applies at *all* widths; a `md:` utility overrides it at ≥768px. Today, many components express their (desktop) layout in **unprefixed** utilities, so those styles currently apply on every screen.

**The re-pin rule.** To change mobile without touching desktop:

> Put the **mobile** value in the unprefixed base, and **re-pin the current value at `md:`**.

Example — the app shell's main padding:
```diff
- <main className="max-w-7xl mx-auto px-6 py-10">
+ <main className="max-w-7xl mx-auto px-4 py-5 pb-24 md:px-6 md:py-10 md:pb-10">
```
At ≥768px this resolves to `px-6 py-10` exactly as before; at <768px it's the tighter mobile padding plus bottom room for the tab bar.

**Invariants for every change:**
1. Never edit or delete an existing `md:` / `lg:` / `xl:` utility.
2. Never change markup that only renders at ≥768px.
3. New mobile-only components are hidden at desktop with `md:hidden`; the desktop chrome they replace is hidden on mobile with `hidden md:flex` (or `md:block`).
4. Components already correct at 390px (e.g. `AnimeGrid` = `grid-cols-2 …`, `DetailHero`, `ComparePage`) are left **untouched**.

**Net effect:** the ≥768px render is provably unchanged because no rule that applies at ≥768px is modified.

---

## 7. New mobile chrome components

All three are **mobile-only** (`md:hidden`) and live in `frontend/src/layout/`. The existing desktop `Header`/`NavBar` are unchanged except for being hidden below `md` (Section 9).

### 7.1 `BottomTabBar`

Fixed bottom navigation, the spine of the mobile app.

- **Container:** `<nav>` — `fixed inset-x-0 bottom-0 z-40 md:hidden` · `bg-bg/80 backdrop-blur-xl border-t border-border` · bottom padding for the home indicator via `style={{ paddingBottom: "env(safe-area-inset-bottom)" }}`.
- **Row:** `flex` with each item `flex-1`.
- **5 items** (4 `NavLink` + 1 More button), each: `flex flex-col items-center justify-center gap-0.5` · `min-h-[56px] py-2` (≥44px hit area) · icon 22px · label `text-[10px] font-mono tracking-wide`.
- **States:** active = `text-amber` (NavLink `isActive`, also set `aria-current="page"`); inactive = `text-text-muted` with `hover:text-text`. Optional 2px amber top-indicator bar on the active tab.
- **Tabs (icon — lucide-react):** Discover (`Compass`, `/discover`) · Schedule (`CalendarDays`, `/schedule`) · Watchlist (`Bookmark`, `/watchlist`) · For you (`Sparkles`, `/for-you`) · More (`MoreHorizontal`, button — opens `MoreSheet`). The More item shows `text-amber` while the sheet is open.

Reference skeleton (illustrative — generator may refine, must keep classes/behavior):
```tsx
export function BottomTabBar({ onOpenMore, moreOpen }: { onOpenMore: () => void; moreOpen: boolean }) {
  const base = "flex-1 flex flex-col items-center justify-center gap-0.5 min-h-[56px] py-2 text-[10px] font-mono tracking-wide";
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 md:hidden bg-bg/80 backdrop-blur-xl border-t border-border"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="flex">
        {TABS.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to}
            className={({ isActive }) => cn(base, isActive ? "text-amber" : "text-text-muted hover:text-text")}>
            <Icon size={22} strokeWidth={1.8} /><span>{label}</span>
          </NavLink>
        ))}
        <button type="button" onClick={onOpenMore} aria-label="More"
          className={cn(base, moreOpen ? "text-amber" : "text-text-muted hover:text-text")}>
          <MoreHorizontal size={22} strokeWidth={1.8} /><span>More</span>
        </button>
      </div>
    </nav>
  );
}
```

### 7.2 `MoreSheet`

Bottom sheet listing secondary destinations + account controls.

- **Overlay:** `fixed inset-0 z-50 md:hidden`, backdrop `bg-black/60 backdrop-blur-sm` (framer-motion fade), click-to-close.
- **Panel:** anchored bottom — `rounded-t-2xl bg-bg-elevated border-t border-border` · `max-h-[85vh] overflow-y-auto` · bottom padding `env(safe-area-inset-bottom)`. Enter: slide up `y: "100%" → 0` with `transitions.spring`; exit reverses. Optional drag-to-dismiss (`drag="y"`, close when dragged past ~96px).
- **Grab handle:** centered `w-9 h-1 rounded-full bg-border-strong` at top, `my-3`.
- **Destinations:** 3-column grid of tappable tiles (`grid grid-cols-3 gap-2 p-4`). Each tile: `GlassCard`-style, `flex flex-col items-center justify-center gap-1.5 min-h-[76px] rounded-lg`, icon 22px + `text-xs` label. Items (icon): Seasonal (`Leaf`) · Collections (`Library`) · Stats (`BarChart3`) · Activity (`Activity`) · Compare (`Scale`) · Chat (`MessageCircle`). Tapping navigates and closes the sheet.
- **Divider**, then **account block** (`p-4 space-y-3`):
  - If signed in: display name (`user.display_name ?? user.username`) + a `Button variant="ghost" size="sm"` **Sign out** (calls `signOut`). If signed out: a primary **Sign in** button → `/auth`.
  - **NSFW toggle row:** label "Show Ecchi content" + the existing eye/eye-off control (port the SVG + `aria-pressed` behavior from `Header`'s `NsfwToggle`, bound to `useNsfw`). 44px hit area.
- **A11y:** `role="dialog" aria-modal="true"`, focus moves into the sheet on open, Escape closes, focus returns to the More button on close. Lock body scroll while open.

### 7.3 `MobileHeader`

Slim top app bar replacing the dense desktop header on mobile.

- `<header>` — `sticky top-0 z-30 md:hidden` · `h-14` · `bg-bg/70 backdrop-blur-xl backdrop-saturate-150 border-b border-border` · `flex items-center px-4`.
- **Brand:** the Bingery wordmark + amber dot, ported from `Header` — `Link to="/"`, `font-display text-xl text-amber` with the `w-2 h-2 rounded-full bg-amber shadow-[…]` dot. Left-aligned.
- **Right action (recommended):** a 44px icon button (`Search`, lucide) → navigates to `/discover`. Optional; omit if you prefer a bare wordmark.
- No nav links and no NSFW/auth here — those live in the tab bar / More sheet.

---

## 8. Modal → responsive bottom sheet

Modify the shared `@/design/Modal` so every modal in the app becomes a native bottom sheet on mobile while the desktop dialog is unchanged.

- **≥768px (`md:`):** keep today's behavior exactly — backdrop, centered panel, `max-w-[640px]` (or `maxWidth` prop), `scale 0.96→1` + `y:8→0` enter, `max-h-[92vh]`, Escape-to-close.
- **<768px:** the panel docks to the bottom — `fixed inset-x-0 bottom-0`, full width, `rounded-t-2xl` (no side radius), `max-h-[85vh] overflow-y-auto`, grab handle at top, slide-up enter (`y:"100%"→0`, `transitions.spring`), `padding-bottom: env(safe-area-inset-bottom)`. Backdrop and Escape behavior unchanged.
- Implementation approach: branch the panel's positioning/rounding/animation on a `md` boundary. Prefer Tailwind responsive classes for static styles; for the framer-motion `initial/animate/exit` that differ by breakpoint, read a `matchMedia("(min-width: 768px)")` value (or a small `useIsDesktop` hook) and pick the variant. Keep the desktop variant values identical to the current file.
- This automatically upgrades every consumer: `CollectionForm`, `AddToCollection`, `AnimePicker`, and any other `Modal` user — verify each renders well as a sheet, but no per-consumer code changes should be required.

---

## 9. AppShell & Header integration

**`AppShell`** (`frontend/src/layout/AppShell.tsx`):
- Keep `<Header />` (now desktop-only) and add the mobile chrome + sheet state:
```tsx
const [moreOpen, setMoreOpen] = useState(false);
// …
<Header />                                  {/* desktop-only after the Header change below */}
<MobileHeader />                            {/* md:hidden */}
<main className="max-w-7xl mx-auto px-4 py-5 pb-24 md:px-6 md:py-10 md:pb-10">
  <PageTransition />
</main>
<BottomTabBar onOpenMore={() => setMoreOpen(true)} moreOpen={moreOpen} />
<MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
```
- The `pb-24` base keeps page content clear of the fixed tab bar; `md:pb-10` restores desktop.

**`Header`** (`frontend/src/layout/Header.tsx`):
- Make the entire desktop header mobile-hidden with the **minimal** change: add `hidden md:block` to its root `<header>` element (the header element itself is `display:block`; its inner row stays `flex`). Its internal markup is otherwise **untouched** (preservation). The `NsfwToggle` SVG/logic is reused by `MoreSheet` — extract it to a shared location or duplicate it; do not alter the desktop instance's behavior.

---

## 10. Global pattern catalog (apply wherever the pattern appears, all gated `<768px`)

1. **Grids** — ensure a 1- or 2-column mobile base with desktop counts re-pinned at `md:`/`lg:`. Most grids already comply (`AnimeGrid` `grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6`; `DetailHero` stats `grid-cols-2 md:grid-cols-4`; `ComparePage`/`Chat` cards `sm:grid-cols-2`). Fix only stragglers that force ≥2 columns with no mobile fallback.
2. **Fixed widths** — any fixed pixel width that can exceed ~360px goes fluid on mobile (`w-full` / `max-w-full`), desktop width re-pinned at `md:`. (Most `*-[…px]` arbitrary values in the app are small posters/thumbnails that already fit; verify, don't blanket-change.)
3. **Touch targets** — small interactive elements get a 44px min hit area on mobile and restore at `md:`. Known cases: the NSFW toggle and the schedule prev/next chevrons are 36px (`h-9 w-9`) → `h-11 w-11 md:h-9 md:w-9`. Do **not** resize the shared `Button`.
4. **Type & spacing** — down-scale oversized desktop type on mobile via base+`md:` pairs (e.g. schedule day number `text-[18px] md:text-[24px]`, episode title `text-[17px] md:text-[21px]`). Tighten generous desktop gaps/padding on mobile only.
5. **Horizontal-scroll chip rows are fine** — Discover `FilterBar`, Watchlist `StatusTabs`, and the Stats `ActivityHeatmap` already use `overflow-x-auto` and are an acceptable mobile pattern. Keep them (ensure they don't cause page-level overflow; body already has `overflow-x: hidden`).

---

## 11. Per-page inventory (full sweep) + file manifest

Effort tiers reflect the actual current code.

**Tier A — verify only (likely zero/trivial changes):** Discover, Watchlist, Seasonal, For you, Collections list (`AnimeGrid`-based, already 2-up); Detail page top (`DetailHero` already responsive); Compare (`ComparePage` already stacks). Action: load at 390px, confirm no overflow, fix any stray spacing.

**Tier B — light tuning:**
- **Detail page** — confirm `RatingPanel` card and `RelatedStrip`/`SimilarStrip` grids read well full-width; tighten section spacing. *Optional flag:* `DetailHero` uses `LiquidGLSurface` (WebGL) — verify it isn't janky on a mid phone; if so, consider a static fallback below `md` (not required).
- **Chat** — bubbles/composer already fine; tune the header so the mode pills (Recommend/Rate/Onboard) don't crowd the title at 390px (e.g. let them wrap to a full-width row); consider `h-[60vh] md:h-[68vh]` for the scroller so the card clears the tab bar.
- **Stats** — verify `OverviewCards` grid is 1–2 col on mobile; ensure `RatingHistogram` and charts fit width; heatmap horizontal-scroll stays.
- **Activity**, **Auth**, **Landing** — center/scale type; verify forms and hero fit 390px.
- **Episode rows** (`EpisodeRow`) — tighten `gap-[18px]`→smaller and `text-[21px]`→`text-[17px]` on mobile via `md:` re-pin; the `grid-cols-[60px_1fr_auto]` poster/meta/badge layout is otherwise fine.

**Tier C — real mobile layout work:**
- **Schedule `DayStrip`** (the hard one) — today a single flex row: `[prevBtn] [month/week label (hidden <sm)] [grid-cols-7 chips, flex-1] [nextBtn]`, `sticky top-0 z-30`. Mobile redesign:
  - Stack into two rows on mobile, single row on desktop (`flex-col md:flex-row` on the inner container). **Row 1 (mobile):** month/week label (now shown) on the left, prev/next chevrons on the right. **Row 2 (mobile):** the `grid-cols-7` day chips full-width (~44px each at 390px, since prev/next no longer share the row).
  - Down-scale chip internals on mobile: day number `text-[18px] md:text-[24px]`; tighten chip padding.
  - Chevron buttons → 44px on mobile (`h-11 w-11 md:h-9 md:w-9`).
  - **Sticky coordination:** the strip sits below the `MobileHeader` (h-14), so `sticky top-14 md:top-0`. Desktop `top-0` unchanged.
  - Re-pin every desktop value at `md:` so the desktop strip is identical.
- **Modal → sheet** — Section 8 (global, once).
- **Chrome** — Sections 7 & 9 (global, once).

**File manifest**

*New (all `frontend/src/layout/`):* `BottomTabBar.tsx`, `MoreSheet.tsx`, `MobileHeader.tsx`. *(Optional)* a `useIsDesktop` hook in `frontend/src/lib/` for the Modal breakpoint branch.

*Modified:* `layout/AppShell.tsx` (mount chrome + main padding), `layout/Header.tsx` (add `hidden md:block`; share `NsfwToggle`), `design/Modal.tsx` (responsive sheet), `features/schedule/DayStrip.tsx` (mobile stack + scale), `features/schedule/EpisodeRow.tsx` (type/gap tuning), `features/chat/ChatPage.tsx` (header pills + scroller height), plus small spacing tweaks discovered during the Tier A/B verification pass.

---

## 12. Verification & acceptance criteria

A change is acceptable only when **both** hold:

1. **Mobile works** — at 390px (and a 360px sanity check), every route: no horizontal scroll, no clipped/overlapping content, tab bar + More sheet reachable with a thumb, content never hidden behind the tab bar, modals open as sheets.
2. **Desktop unchanged** — at ≥768px the app is visually identical to current production. Spot-check Detail, Discover, Schedule, Chat, Stats at 768px / 1024px / 1280px.

Automated guards (from the prior handoff):
- `& 'frontend/node_modules/.bin/tsc.cmd' -b frontend` → exit 0.
- `python -m pytest -q` → 301 passed (backend untouched; run as regression guard).
- `python -m pytest tests/test_related.py -v` → 13 passed.
- Live smoke after deploy: `curl -s https://bingery.fly.dev/api/health` → 200.

---

## 13. Out of scope

- Any backend / API change.
- New npm dependencies.
- Route/URL changes (the nav components reuse existing routes).
- Tablet-specific (768–1023px) redesign — that range keeps the desktop layout.
- Desktop visual changes of any kind.
- Reworking the font-loading mismatch (`Instrument Serif`/`Geist` tokens vs bundled Fraunces/Inter) — pre-existing, unrelated.
