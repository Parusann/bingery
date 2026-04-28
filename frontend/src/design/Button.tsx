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

const variantClass: Record<Variant, string> = {
  primary:
    "bg-amber text-bg hover:bg-amber-soft focus-visible:ring-2 focus-visible:ring-amber/60",
  ghost:
    "bg-transparent text-text border border-border hover:border-border-strong hover:bg-white/[0.04]",
  glass:
    "bg-surface text-text border border-border backdrop-blur-md hover:bg-surface-strong glass-edge",
  danger:
    "bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25",
};

const sizeClass: Record<Size, string> = {
  sm: "h-8 px-3 text-xs rounded-md",
  md: "h-10 px-4 text-sm rounded-lg",
  lg: "h-12 px-6 text-base rounded-xl",
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
