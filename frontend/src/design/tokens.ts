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
