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

// Hierarchy, restored: ONE unmistakable primary per view — solid amber with
// dark text. Everything else recedes behind it: ghost = amber-tinted outline
// glass (the old "primary" look, demoted), glass = neutral surface, danger =
// the same pill/glass language in the danger hue.
const variantClass: Record<Variant, string> = {
  primary:
    "font-semibold text-bg bg-gradient-to-b from-amber-hi to-amber border border-amber-hi/60 " +
    "shadow-[0_14px_40px_-12px_rgba(239,171,129,0.5),inset_0_1px_0_rgba(255,235,220,0.65)] " +
    "hover:from-amber-hi hover:to-amber-deep hover:-translate-y-px " +
    "active:translate-y-0 " +
    "focus-visible:ring-amber/70",
  ghost:
    "text-text border border-amber/35 bg-surface backdrop-blur-md " +
    "shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] " +
    "hover:bg-amber/[0.08] hover:border-amber/60 hover:-translate-y-px active:translate-y-0 " +
    "focus-visible:ring-amber/60",
  glass:
    "text-text bg-surface border border-border backdrop-blur-md glass-edge " +
    "hover:bg-surface-strong hover:border-border-strong " +
    "focus-visible:ring-amber/60",
  danger:
    "text-danger bg-danger/10 border border-danger/40 backdrop-blur-md " +
    "shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] " +
    "hover:bg-danger/20 hover:border-danger/60 " +
    "focus-visible:ring-danger/60",
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
        "transition-all outline-none focus-visible:outline-none",
        "focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
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
