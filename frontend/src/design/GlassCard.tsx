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

// Glass surface on elevation tokens: resting cards sit at e2, elevated
// (modals, spotlit panels) at e3 with a stronger border.
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
        "relative rounded-xl border backdrop-blur-md",
        elevated ? "border-border-strong shadow-e3" : "border-border shadow-e2",
        toneClass[tone],
        className
      )}
    >
      {children}
    </div>
  );
}
