// Bingery design tokens — the single source of truth for color, space,
// radius, type, elevation, and motion. tokens.js / tokens.d.ts are mirrors
// (kept for the tailwind-config loader); keep all three in sync.
//
// Direction: "warm light on a cool dark stage." The stage stays violet-black;
// every foreground layer — text, borders, glass — is warm ink, and a single
// amber ramp carries all interactive warmth. Gold is reserved for stars/
// favorites. Violet is the cool counterpoint.

export const palette = {
  // ── Stage ──────────────────────────────────────────────────────────
  bg: "#080510",
  bgElevated: "#0f0a1a",

  // ── Warm glass layers (ink-tinted, never pure white) ───────────────
  surface: "rgba(243,236,228,0.04)",
  surfaceStrong: "rgba(243,236,228,0.08)",
  border: "rgba(243,236,228,0.10)",
  borderStrong: "rgba(243,236,228,0.18)",

  // ── Accent: one amber ramp (hi = highlight, deep = pressed) ────────
  amber: "#efab81",
  amberHi: "#ffd0ad",
  amberDeep: "#d98f63",
  amberSoft: "#d9b899",

  // ── Cool counterpoint ──────────────────────────────────────────────
  violet: "#b89ac4",
  violetSoft: "#9e86a9",

  // ── Warm ink text ──────────────────────────────────────────────────
  text: "rgba(243,236,228,0.95)",
  textMuted: "rgba(243,236,228,0.68)",
  textDim: "rgba(243,236,228,0.52)",

  danger: "#e78a8a",
  success: "#9bc9ab",

  // ── Legacy schedule dialect — now aliases of the unified ramp ──────
  // (peach* == amber ramp; ink/mute/line == warm neutrals above)
  peach: "#efab81",
  peachHi: "#ffd0ad",
  peachDeep: "#d98f63",
  sage: "#9BB8A8",
  sageBg: "rgba(155,184,168,0.10)",
  sageBd: "rgba(155,184,168,0.38)",
  gold: "#f4cf90", // reserved meaning: stars, favorites, watchlist highlights
  goldBd: "rgba(244,207,144,0.42)",
  goldGlow: "rgba(244,207,144,0.18)",
  ink: "#f3ece4",
  ink2: "#cfc5b9",
  mute: "#9a90a2",
  mute2: "#6b6274",
  line: "rgba(243,236,228,0.08)",
  line2: "rgba(243,236,228,0.14)",
  rowBg: "rgba(243,236,228,0.03)",
  rowBgHover: "rgba(243,236,228,0.055)",
  rowBd: "rgba(243,236,228,0.07)",
} as const;

export const radius = {
  sm: "6px",
  md: "10px",
  lg: "16px",
  xl: "22px",
  xxl: "28px",
  pill: "9999px",
} as const;

// 4px grid. Anything not on this grid is a bug, not a design decision.
export const space = {
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "24px",
  xxl: "40px",
} as const;

export const font = {
  display: "Fraunces, ui-serif, Georgia, serif",
  body: "Inter, ui-sans-serif, system-ui, -apple-system, sans-serif",
  mono: '"JetBrains Mono", ui-monospace, SFMono-Regular, monospace',
} as const;

// Elevation tiers. e2 is identical to the legacy `.glass-edge` utility so
// existing surfaces don't shift; e1 is for resting cards/rows, e3 for
// modals and floating chrome. Glows are focus/emphasis, not decoration.
export const elevation = {
  e1: "inset 0 1px 0 rgba(255,255,255,0.05), 0 8px 24px -16px rgba(0,0,0,0.5)",
  e2: "inset 0 1px 0 rgba(255,255,255,0.08), inset 0 -1px 0 rgba(0,0,0,0.18), 0 24px 48px -24px rgba(0,0,0,0.5)",
  e3: "inset 0 1px 0 rgba(255,255,255,0.09), 0 32px 80px -32px rgba(0,0,0,0.7)",
  glowAmber: "0 0 0 1px rgba(239,171,129,0.35), 0 12px 40px -12px rgba(239,171,129,0.30)",
  glowGold: "0 0 0 1px rgba(244,207,144,0.42), 0 12px 40px -12px rgba(244,207,144,0.25)",
} as const;

// Motion vocabulary. Durations in seconds (framer-motion convention).
// fast  = hover/press feedback        base = entrances, reveals
// slow  = layout shifts, heroes       glacial = ambient atmosphere only
export const motion = {
  ease: [0.22, 1, 0.36, 1] as const, // standard decel — most things
  easeOut: [0.16, 1, 0.3, 1] as const, // stronger decel — hero entrances
  easeIn: [0.3, 0, 0.8, 0.15] as const, // exits only
  duration: {
    fast: 0.16,
    base: 0.26,
    slow: 0.42,
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
