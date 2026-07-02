import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { palette } from "./tokens";

interface Props {
  color?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

// Tinted chip. Default is the system amber (was an off-palette indigo).
// `color` accepts any hex — genre colors pass through genreColor().
export function Badge({ color = palette.amber, children, className, style }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded",
        "border backdrop-blur-sm",
        className
      )}
      style={{
        background: color + "1C",
        color,
        borderColor: color + "36",
        ...style,
      }}
    >
      {children}
    </span>
  );
}
