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
