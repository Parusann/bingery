import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/cn";

interface Props {
  color?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function Badge({ color = "#6366f1", children, className, style }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-semibold rounded",
        "border backdrop-blur-sm",
        className
      )}
      style={{
        background: color + "18",
        color,
        borderColor: color + "30",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
