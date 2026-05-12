import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  leading?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, error, leading, className, id, ...rest },
  ref
) {
  const domId = id ?? rest.name ?? undefined;
  return (
    <label htmlFor={domId} className="flex flex-col gap-1.5 text-sm">
      {label ? <span className="text-text-muted">{label}</span> : null}
      <div
        className={cn(
          "flex items-center gap-2 h-10 px-3 rounded-lg",
          "bg-surface border border-border focus-within:border-border-strong",
          "focus-within:ring-1 focus-within:ring-amber/40",
          error && "border-danger/60 focus-within:ring-danger/40"
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
