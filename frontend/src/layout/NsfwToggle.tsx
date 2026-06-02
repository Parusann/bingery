import { useNsfw } from "@/stores/nsfw";
import { cn } from "@/lib/cn";

/**
 * Ecchi visibility toggle. Extracted from the desktop Header so both the
 * Header (desktop) and the MoreSheet (mobile) share one implementation.
 *
 * `size` controls the hit area: "sm" = 36px (the original desktop size),
 * "lg" = 44px (mobile touch target). Desktop callers MUST pass size="sm"
 * so the desktop instance is byte-identical to before.
 */
export function NsfwToggle({ size = "sm" }: { size?: "sm" | "lg" }) {
  const visible = useNsfw((s) => s.visible);
  const toggle = useNsfw((s) => s.toggle);
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={visible}
      aria-label={visible ? "Hide Ecchi content" : "Show Ecchi content"}
      title={
        visible
          ? "Ecchi visible — click to hide. (Hentai is always hidden.)"
          : "Ecchi hidden — click to show. (Hentai is always hidden.)"
      }
      className={cn(
        "rounded-pill border border-amber/30 bg-white/[0.04] backdrop-blur-md text-text-muted",
        "hover:text-amber hover:border-amber/55 hover:bg-amber/[0.08] transition-colors",
        "flex items-center justify-center shrink-0",
        size === "lg" ? "w-11 h-11" : "w-9 h-9"
      )}
    >
      {visible ? (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-6.5 0-10-7-10-7a19.83 19.83 0 0 1 4.06-4.94" />
          <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c6.5 0 10 7 10 7a19.81 19.81 0 0 1-3.17 4.19" />
          <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
          <line x1="2" y1="2" x2="22" y2="22" />
        </svg>
      )}
    </button>
  );
}
