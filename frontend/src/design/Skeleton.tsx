import { cn } from "@/lib/cn";

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
    <div
      className={cn(
        "relative overflow-hidden bg-white/[0.04]",
        r,
        className
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.05] to-transparent animate-[shimmer_1.6s_infinite]" />
      <style>{`@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}`}</style>
    </div>
  );
}
