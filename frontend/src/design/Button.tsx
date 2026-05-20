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

// Glass-peach button family — matches the landing page's `.btn` and
// `.btn.primary` aesthetic: pill shape, soft amber border, backdrop blur,
// inset top highlight, gentle lift on hover.
const variantClass: Record<Variant, string> = {
  primary:
    "text-text border border-amber/55 bg-gradient-to-b from-amber/[0.18] to-amber/[0.06] " +
    "backdrop-blur-md " +
    "shadow-[0_14px_40px_-12px_rgba(244,182,144,0.45),inset_0_1px_0_rgba(255,220,200,0.20)] " +
    "hover:from-amber/[0.28] hover:to-amber/[0.10] hover:border-amber/70 hover:-translate-y-px " +
    "focus-visible:ring-2 focus-visible:ring-amber/60",
  ghost:
    "text-text border border-amber/30 bg-white/[0.04] backdrop-blur-md " +
    "shadow-[0_8px_30px_-10px_rgba(244,182,144,0.18),inset_0_1px_0_rgba(255,255,255,0.06)] " +
    "hover:bg-amber/[0.08] hover:border-amber/55 hover:-translate-y-px " +
    "hover:shadow-[0_14px_40px_-10px_rgba(244,182,144,0.35),inset_0_1px_0_rgba(255,255,255,0.10)]",
  glass:
    "bg-surface text-text border border-border backdrop-blur-md hover:bg-surface-strong glass-edge",
  danger:
    "bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25",
};

const sizeClass: Record<Size, string> = {
  sm: "h-8 px-4 text-xs rounded-pill",
  md: "h-10 px-5 text-sm rounded-pill",
  lg: "h-12 px-7 text-base rounded-pill",
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
