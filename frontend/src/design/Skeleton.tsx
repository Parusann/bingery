import { cn } from "@/lib/cn";

// Loading placeholder. Warm ink base with a faint warm shimmer — matches the
// glass surfaces it stands in for. The shimmer is CSS-only, so the global
// prefers-reduced-motion kill-switch in index.css freezes it automatically.
export function Skeleton({
  className,
  rounded = "md",
}: {
  className?: string;
  rounded?: "sm" | "md" | "lg" | "full";
}) {
  const r = {
    sm: "rounded-sm",
    md: "rounded-md",
    lg: "rounded-lg",
    full: "rounded-full",
  }[rounded];
  return (
    <div className={cn("relative overflow-hidden bg-surface", r, className)}>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[rgba(255,220,200,0.06)] to-transparent animate-[shimmer_1.6s_infinite]" />
      <style>{`@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}`}</style>
    </div>
  );
}
