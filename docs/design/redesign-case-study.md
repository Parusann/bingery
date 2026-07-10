# Bingery — Redesign Case Study

*A full UI/UX elevation pass across every surface of the app: one token system, one motion vocabulary, nine redesigned pages, zero logic changes.*

**Stack:** React 18 · TypeScript · Tailwind · framer-motion · installable PWA
**Scope:** ~45 components across `src/design/` and every feature folder. All data fetching, hooks, stores, routes, and the test suite untouched — the entire pass is presentational.

---

## 1. The problem

The app worked, but it didn't *hold together*. The honest audit before any code:

- **The typefaces weren't rendering at all.** `tokens.ts` declared Instrument Serif and Geist; the build loaded Fraunces, Inter, and JetBrains Mono. Nothing loaded the declared fonts, so every heading fell back to Georgia and body text to system sans. The single biggest reason the app read "default-looking" was a one-line mismatch nobody had noticed.
- **Two design languages were fighting.** The base palette (`surface`/`border`/`amber`) coexisted with a private "schedule revamp" dialect (`ink`/`mute`/`line`/`peach`/`gold`/`sage`) — including a duplicate `Badge` component. Schedule was the strongest surface in the app, and it looked like it came from a different product.
- **Tokens existed but weren't wired.** `space` and `blur` tokens were defined and never connected to Tailwind, so features accumulated magic values: `gap-[18px]`, `text-[17px]`, `h-[70px] w-[52px]`, `rounded-[22px]`, `h-[232px]` skeleton heights hardcoded to mirror a component's implementation detail.
- **Amber meant everything, so it meant nothing.** Page titles, scores, stats, links, buttons, and borders all pulled from the same accent. Six amber numbers in a stats row read as noise, not emphasis.
- **Motion tokens existed and were ignored.** `motion.ts` defined durations/easings; `ChatPage` hardcoded `{ duration: 0.25 }` anyway. Discover cards double-animated (card entrance *and* grid ScrollReveal stacked). No `prefers-reduced-motion` support anywhere except one WebGL component.
- **The heatmap was a GitHub clone** — 10px cells, no labels, no legend, `title` attributes as the only affordance. Borrowed furniture in a product that deserved its own.
- **States lacked design.** Empty states were single sentences. Error states were bare red text. Four slightly-different signed-out blocks. Skeletons that didn't match the layouts they stood in for.

## 2. Design direction

**"Warm light on a cool dark stage."**

Anime is watched at night. The direction leans into that: a violet-black stage (`#080510`), warm ink foregrounds (`rgba(243,236,228,…)` — never pure white), and a single amber ramp carrying all interactive warmth, like lamplight on a dark room. Fraunces (a warm, slightly nostalgic serif) gives editorial voice to display moments; JetBrains Mono handles labels and numerals like film-can stenciling; Inter does the quiet work in between.

**What was deliberately rejected:**
- *A trendy neutral rebuild* (shadcn-style zinc + white) — competent, anonymous, and indistinguishable from every AI-generated dashboard. The existing warm identity was the most ownable thing the app had; the job was to finish it, not replace it.
- *Amber everywhere* — the accent was demoted from headings and stats into a strict role: **amber = interactive/emphasis, gold = stars & favorites, sage = dub, violet = cool counterpoint.** Color now carries meaning.
- *Raw saturated genre colors* — the old genre palette screamed against the dark stage. Every genre hue was retuned to dusty, film-grade values at consistent perceived lightness.
- *Replacing the schedule's look* — it was the best surface, so its dialect (`peach`/`ink`/`gold`) was **promoted into the system as aliases of the unified ramp** rather than deleted. The schedule kept its identity; the rest of the app rose to meet it.

## 3. The system

One source of truth in `src/design/tokens.ts`, wired fully into Tailwind.

**Color roles** (excerpt):

| Role | Token | Value |
|---|---|---|
| Stage | `bg` / `bg-elevated` | `#080510` / `#0f0a1a` |
| Warm glass | `surface` / `surface-strong` | warm ink @ 4% / 8% |
| Accent ramp | `amber` / `amber-hi` / `amber-deep` | `#efab81` / `#ffd0ad` / `#d98f63` |
| Reserved | `gold` (stars/favorites) | `#f4cf90` |
| Sub / Dub | `amber` / `sage` | `#efab81` / `#9BB8A8` |
| Text | `text` / `text-muted` / `text-dim` | warm ink @ 95 / 68 / 52% |

`text-dim` was bumped from 42% → 52% specifically to clear AA contrast (~4.7:1) for the mono micro-labels it's used on.

**Type scale** — semantic, fluid at the top end, with Tailwind's default scale below it:
`display-hero` (clamp 2.1–3.35rem) → `display` → `title` → `heading` → `body-lg` → `caption` → `micro` (mono, letter-spaced, uppercase). The recurring page-header pattern — mono amber eyebrow + ink display serif — comes from this scale, not per-page decisions. Every stat, score, count, date, and countdown sets `.tnum` (tabular lining numerals).

**Elevation** — three tiers instead of one-off shadow strings: `e1` (resting cards) / `e2` (primary surfaces — identical to the legacy `glass-edge` so nothing shifted) / `e3` (floating chrome), plus `glow-amber` / `glow-gold` reserved for emphasis (the chat seed card, the current-title card in a franchise).

**Radius** — full override, not extend: `sm 6 / md 10 / lg 16 / xl 22 / pill`. Legacy `rounded-2xl` usages snap onto the token scale automatically.

**Motion vocabulary** — tokens as the only legal source: `fast 160ms` (hover/press) / `base 260ms` (entrances) / `slow 420ms` (heroes, poster zooms) / `glacial 700ms` (ambient only), with three easings and two springs. `<MotionConfig reducedMotion="user">` wraps the app; a global CSS kill-switch covers non-framer animation. Before/after in practice:

```tsx
// before — per-file improvisation
transition={{ duration: 0.25, ease: "easeOut" }}

// after — one voice
transition={transitions.ease}
```

Performance is part of craft: `backdrop-blur` (used on ~25 surfaces) was capped globally — Tailwind's 40–64px defaults were costing GPU time the design didn't need.

## 4. Key decisions, per surface

**Discover** — The card hover is the signature: a quiet −4px lift, warm border, 420ms poster zoom, bottom scrim, title warming to `amber-hi`. The double entrance animation was removed (the grid's ScrollReveal owns entrances; the card owns hover). Sort became a real segmented control; the genre rail fades at its edge to signal scrollability. Trade-off: hover reveals no extra metadata — tested busier overlays and they fought the poster art.

**Anime detail** — The hero got compositional drama without new content: banner scaled 105% behind a two-axis vignette and warm wash, poster lifted to `e3` with a hairline ring, native title as italic Fraunces, and the score as the *only* amber number in the stat row. The franchise strip's current title sits under a `glow-amber` instead of a hard ring; estimated dub dates show "~Jul 9" rather than a fake-precise countdown — precision matching what we actually know.

**Guide chat** — Assistant bubbles carry an amber spine (a quote, not a chrome element); the typing indicator became three staggered dots + a mono "GUIDE IS THINKING" caption; `**bold**` in messages renders as amber-hi semibold instead of jarring serif; the amber-ringed seed card and quick-action pills survived intact with focus rings added. The offline banner is a designed state, not an apology.

**Schedule** — Already the best surface; it was *harmonized*, not redesigned. Its dialect became system aliases, magic values snapped to the grid, glyphs became lucide icons, and its sub/dub color language (amber/sage) was exported app-wide — the detail page's next-episode pills now match. Chips were corrected back to `rounded-lg` after the radius override would have ballooned them.

**Watchlist** — Status colors retuned to the dusty ramp; *your* score reads gold everywhere (the reserved star color). The genre filter collapsed from a flat rail of every genre into a Genres trigger + popover, with only *selected* genres inline as removable chips — scales to dozens of options without clutter.

**For You** — Recommendation reasons became quote cards: amber spine + italic Fraunces, echoing the Guide's voice (the same system element meaning "the app is speaking"). The taste profile gained a loading skeleton that mirrors its final layout.

**Stats** — The GitHub-style heatmap was deleted, not polished. Its replacement, "Your rhythm," answers questions the data can actually support: an editorial headline ("Most of your watching lands on Saturdays — 31% of the year"), a 12-month film strip whose frames expose brighter with activity, a weekday chart with the binge night spotlit, and three earned facts (biggest day, longest streak, busiest month) — all derived client-side from the same `{date, count}` cells. Same component name and props; zero API changes.

**Collections** — Cards became anime box-sets: colored spine edge, textured cover, a huge ghosted italic monogram. Generative identity (the list payload has no artwork) that reads as an object, not a gradient rectangle.

**Activity** — A real timeline: spine rail, kind-coded icon nodes (gold = stars/favorites, amber = watching, violet = collections, sage = votes/reports), mono day dividers (Today / Yesterday / Jun 30), and gold score chips on ratings. Grouping is pure presentation over the existing paginated feed.

**Auth** — The mode switch became the system segmented control; the verification code input went mono, centered, letter-spaced. Every test-locked string ("Sign in", "Create account", "Join the waitlist", "Wrong email? Go back") is byte-identical.

## 5. Craft details

**Accessibility**
- AA contrast audited on the dark stage; `text-dim` explicitly re-tuned to pass for the small mono labels it decorates.
- One focus language: a global warm `:focus-visible` outline baseline, with component-level `focus-visible:ring-2 ring-amber/60` (+ offset on cards) fitted to each shape. Chips, pills, rows, tabs, and tiles are all keyboard-reachable with visible rings.
- `prefers-reduced-motion` respected twice: `<MotionConfig reducedMotion="user">` for framer, a global CSS kill-switch for everything else. The skeleton shimmer freezes automatically.
- Aria surfaces preserved and extended: StarRating's "Rate N of 10" labels, `aria-pressed` on all toggles, `role="img"` summaries on data visualizations, `role="status"`/`role="alert"` on async feedback.

**Every state designed**
- Skeletons mirror the final anatomy of each page (hero skeleton = poster + title + badges; grid skeleton = poster + two text lines) so loading doesn't reflow.
- Empty states share an editorial voice: mono eyebrow + italic Fraunces line + a real action where one exists ("Clear filters").
- Error and success states use the `danger`/`success` tokens with `role` attributes; the chat's offline banner is a first-class designed state.

**Responsive / PWA**
- All 44px tap targets from the prior mobile pass preserved (chips, pills, back-to-top, code inputs).
- Mobile-specific art direction kept and extended: the schedule's two-row day strip, safe-area insets on the tab bar and sheet, drag-to-dismiss on the More sheet.
- The bottom tab bar's active glow and the wordmark's brand dot now carry the current amber — the last traces of the old accent value are gone.

## 6. Before / after gallery

*(Screenshots to be captured — see shot list below.)*

| | |
|---|---|
| ![Discover — before](./assets/before-discover.png) | ![Discover — after](./assets/after-discover.png) |

*Discover: fallback fonts → the full type system; double-animating cards → one entrance, one signature hover (lift + zoom + warm title).*

| | |
|---|---|
| ![Anime detail — before](./assets/before-detail.png) | ![Anime detail — after](./assets/after-detail.png) |

*Detail: flat banner + generic stat row → vignetted hero, e3 poster, italic native title, score as the only amber number.*

| | |
|---|---|
| ![Guide chat — before](./assets/before-chat.png) | ![Guide chat — after](./assets/after-chat.png) |

*Chat: pulsing dots → the "Guide is thinking" moment; serif bold-in-body → amber-hi emphasis; spined assistant bubbles.*

| | |
|---|---|
| ![Schedule — before](./assets/before-schedule.png) | ![Schedule — after](./assets/after-schedule.png) |

*Schedule: private dialect → the system's origin story; same identity, now app-wide.*

| | |
|---|---|
| ![Watchlist — before](./assets/before-watchlist.png) | ![Watchlist — after](./assets/after-watchlist.png) |

*Watchlist: flat genre rail → popover + selected chips; gold scores; status colors on the dusty ramp.*

| | |
|---|---|
| ![For You — before](./assets/before-foryou.png) | ![For You — after](./assets/after-foryou.png) |

*For You: plain reason text → quote cards with the amber spine.*

| | |
|---|---|
| ![Stats — before](./assets/before-stats.png) | ![Stats — after](./assets/after-stats.png) |

*Stats: GitHub-clone heatmap → "Your rhythm": film strip, weekday spotlight, earned facts.*

| | |
|---|---|
| ![Collections — before](./assets/before-collections.png) | ![Collections — after](./assets/after-collections.png) |

*Collections: gradient rectangles → box-sets with spines and ghost monograms.*

| | |
|---|---|
| ![Activity — before](./assets/before-activity.png) | ![Activity — after](./assets/after-activity.png) |

*Activity: flat list → timeline with kind-coded nodes and day dividers.*

| | |
|---|---|
| ![Auth — before](./assets/before-auth.png) | ![Auth — after](./assets/after-auth.png) |

*Auth: ad-hoc toggle → system segmented control; designed verify step.*

| | |
|---|---|
| ![Mobile — before](./assets/before-mobile.png) | ![Mobile — after](./assets/after-mobile.png) |

*Mobile: preserved tap-target work, now with the system's color/motion voice in the tab bar and sheets.*

### Screenshot shot list

Capture at 1440×900 (desktop) and 390×844 (mobile), dark room, real data seeded:

1. **Discover** — desktop, grid loaded, one card mid-hover (lift + zoom visible), genre rail with an active chip.
2. **Discover mobile** — 390px, 2-col grid + bottom tab bar with active indicator.
3. **Anime detail** — desktop, full hero (banner + poster + stats + description), next-episode pills visible (one sub, one estimated dub).
4. **Guide chat** — desktop, a conversation showing: user bubble, assistant bubble with **bold** text, seed card with SIMILAR TO label, 2×2 card grid, quick-action pills, and the typing indicator (send a message, capture during the wait).
5. **Schedule** — desktop, day strip (with TODAY chip) + one day banner with collage + watchlist group + estimated dub row.
6. **Watchlist** — desktop, genre popover OPEN with 2 genres selected, status tabs visible, large grid with one gold-scored card in view.
7. **Watchlist list view** — desktop or mobile, showing status dots + progress + gold scores.
8. **For You** — desktop, taste profile bars + picks row + two reason quote cards.
9. **Stats** — desktop, full page: overview tiles, histogram, top genres, and "Your rhythm" (film strip + weekday chart + facts).
10. **Collections** — desktop, 3 box-set cards with different spine colors.
11. **Activity** — desktop, timeline with ≥2 day dividers and a gold rating chip.
12. **Auth** — desktop, sign-in card; second shot of the verify step with a partially-entered code.
13. **Empty state** — any page (watchlist filtered to no results) showing the editorial empty treatment + Clear filters.
14. **Loading state** — Discover or detail mid-load showing anatomy-matched skeletons (throttle network to capture).
15. **Focus ring** — any card/chip focused via keyboard (Tab), showing the amber ring — the accessibility receipt.

*Before shots: check out the pre-redesign commit, seed the same data, capture 1:1 the same views.*
