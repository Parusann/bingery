import type { Config } from "tailwindcss";
import { palette, radius, font, elevation } from "./src/design/tokens";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // Full override (not extend): one radius scale, no dual vocabulary.
    // `rounded-2xl` and friends now resolve to tokens instead of Tailwind
    // defaults, so legacy usages snap onto the system automatically.
    borderRadius: {
      none: "0",
      sm: radius.sm,
      DEFAULT: radius.sm,
      md: radius.md,
      lg: radius.lg,
      xl: radius.xl,
      "2xl": radius.xl,
      "3xl": radius.xxl,
      pill: radius.pill,
      full: radius.pill,
    },
    extend: {
      colors: {
        bg: palette.bg,
        "bg-elevated": palette.bgElevated,
        surface: palette.surface,
        "surface-strong": palette.surfaceStrong,
        border: palette.border,
        "border-strong": palette.borderStrong,
        amber: palette.amber,
        "amber-hi": palette.amberHi,
        "amber-deep": palette.amberDeep,
        "amber-soft": palette.amberSoft,
        violet: palette.violet,
        "violet-soft": palette.violetSoft,
        text: palette.text,
        "text-muted": palette.textMuted,
        "text-dim": palette.textDim,
        danger: palette.danger,
        success: palette.success,
        peach: palette.peach,
        "peach-hi": palette.peachHi,
        "peach-deep": palette.peachDeep,
        sage: palette.sage,
        "sage-bg": palette.sageBg,
        "sage-bd": palette.sageBd,
        gold: palette.gold,
        "gold-bd": palette.goldBd,
        "gold-glow": palette.goldGlow,
        ink: palette.ink,
        "ink-2": palette.ink2,
        mute: palette.mute,
        "mute-2": palette.mute2,
        line: palette.line,
        "line-2": palette.line2,
        "row-bg": palette.rowBg,
        "row-bg-hover": palette.rowBgHover,
        "row-bd": palette.rowBd,
      },
      fontFamily: {
        display: [font.display],
        sans: [font.body],
        mono: [font.mono],
      },
      // Semantic type scale. Display sizes are fluid; the old `.text-display`
      // and `.text-display-hero` utilities from index.css now live here so
      // existing markup keeps working with a single source of truth.
      fontSize: {
        "display-hero": ["clamp(2.1rem, 6.5vw, 3.35rem)", { lineHeight: "1.03", letterSpacing: "-0.02em" }],
        display: ["clamp(1.65rem, 5vw, 2.4rem)", { lineHeight: "1.08", letterSpacing: "-0.015em" }],
        title: ["clamp(1.3rem, 3vw, 1.6rem)", { lineHeight: "1.15", letterSpacing: "-0.01em" }],
        heading: ["1.1875rem", { lineHeight: "1.3", letterSpacing: "-0.005em" }],
        "body-lg": ["1.0625rem", { lineHeight: "1.55" }],
        caption: ["0.8125rem", { lineHeight: "1.45" }],
        micro: ["0.6875rem", { lineHeight: "1.2", letterSpacing: "0.12em" }],
      },
      // Elevation tiers + emphasis glows. e2 === legacy `.glass-edge`.
      boxShadow: {
        e1: elevation.e1,
        e2: elevation.e2,
        e3: elevation.e3,
        "glow-amber": elevation.glowAmber,
        "glow-gold": elevation.glowGold,
      },
      // Motion tokens for plain-CSS transitions (framer uses tokens.motion).
      transitionDuration: {
        DEFAULT: "200ms",
        fast: "160ms",
        base: "260ms",
        slow: "420ms",
      },
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(0.22, 1, 0.36, 1)",
        out: "cubic-bezier(0.16, 1, 0.3, 1)",
        in: "cubic-bezier(0.3, 0, 0.8, 0.15)",
      },
      backgroundImage: {
        grain: "url('/grain.svg')",
      },
      // backdrop-filter blur is one of the most expensive things a browser
      // can composite, and Bingery uses it on ~25 surfaces (incl. every
      // grid/list card). Tailwind's defaults go up to 40–64px; cap the whole
      // scale well below that so the frosted-glass look survives at a
      // fraction of the GPU cost (blur cost scales with radius).
      backdropBlur: {
        none: "0",
        sm: "3px",
        DEFAULT: "5px",
        md: "6px",
        lg: "8px",
        xl: "10px",
        "2xl": "12px",
        "3xl": "16px",
      },
    },
  },
  plugins: [],
} satisfies Config;
