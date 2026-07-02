import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  leading?: React.ReactNode;
}

// 44px field (mobile tap-target floor) with a warm focus treatment:
// amber border + soft ring, danger takes over both when errored.
export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, error, leading, className, id, ...rest },
  ref
) {
  const domId = id ?? rest.name ?? undefined;
  return (
    <label htmlFor={domId} className="flex flex-col gap-1.5 text-sm">
      {label ? (
        <span className="text-caption font-medium text-text-muted">{label}</span>
      ) : null}
      <div
        className={cn(
          "flex items-center gap-2 h-11 px-3.5 rounded-lg transition-colors",
          "bg-surface border border-border",
          "focus-within:border-amber/50 focus-within:ring-1 focus-within:ring-amber/35 focus-within:bg-amber/[0.03]",
          error && "border-danger/60 focus-within:border-danger/60 focus-within:ring-danger/40"
        )}
      >
        {leading}
        <input
          ref={ref}
          id={domId}
          className={cn(
            "flex-1 bg-transparent outline-none placeholder:text-text-dim",
            className
          )}
          {...rest}
        />
      </div>
      {error ? <span className="text-xs text-danger">{error}</span> : null}
    </label>
  );
});
