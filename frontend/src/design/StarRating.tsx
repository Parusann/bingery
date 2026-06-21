import { useState } from "react";
import { cn } from "@/lib/cn";

interface Props {
  value: number;
  onChange: (v: number) => void;
  readOnly?: boolean;
  size?: number;
  className?: string;
}

export function StarRating({ value, onChange, readOnly, size = 24, className }: Props) {
  const [hover, setHover] = useState(0);
  const display = hover || value;
  return (
    <div className={cn("w-full sm:w-auto", className)}>
      <div
        className="flex w-full items-center sm:inline-flex sm:w-auto sm:gap-0.5"
        aria-label={`Rating ${value} of 10`}
        onMouseLeave={() => setHover(0)}
      >
        {Array.from({ length: 10 }).map((_, i) => {
          const n = i + 1;
          const on = n <= display;
          return (
            <button
              key={n}
              type="button"
              disabled={readOnly}
              onMouseEnter={() => !readOnly && setHover(n)}
              onClick={() => !readOnly && onChange(n)}
              className={cn(
                "flex flex-1 items-center justify-center py-2 transition-transform sm:flex-none sm:p-0.5",
                !readOnly && "hover:scale-110 cursor-pointer",
                readOnly && "cursor-default"
              )}
              aria-label={`Rate ${n} of 10`}
            >
              <svg
                width={size}
                height={size}
                viewBox="0 0 24 24"
                fill={on ? "#e6a680" : "none"}
                stroke={on ? "#e6a680" : "rgba(255,255,255,0.3)"}
                strokeWidth="2"
                strokeLinejoin="round"
              >
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </button>
          );
        })}
        <span className="ml-2 hidden text-sm text-text-muted tabular-nums sm:inline">
          {display}/10
        </span>
      </div>
      <div className="mt-1 text-center text-sm text-text-muted tabular-nums sm:hidden">
        {display}/10
      </div>
    </div>
  );
}
