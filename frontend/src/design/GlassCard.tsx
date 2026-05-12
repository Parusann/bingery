import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface Props extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  tone?: "default" | "warm" | "cool";
  elevated?: boolean;
}

const toneClass: Record<NonNullable<Props["tone"]>, string> = {
  default: "bg-surface",
  warm: "bg-gradient-to-br from-amber/[0.08] to-transparent",
  cool: "bg-gradient-to-br from-violet/[0.08] to-transparent",
};

export function GlassCard({
  children,
  tone = "default",
  elevated,
  className,
  ...rest
}: Props) {
  return (
    <div
      {...rest}
      className={cn(
        "relative rounded-xl border border-border glass-edge",
        "backdrop-blur-md",
        toneClass[tone],
        elevated && "shadow-[0_24px_60px_-30px_rgba(0,0,0,0.6)]",
        className
      )}
    >
      {children}
    </div>
  );
}
