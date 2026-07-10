import { Link, useNavigate } from "react-router-dom";
import { Search } from "lucide-react";

/**
 * Slim top app bar for mobile. Mobile-only (md:hidden) — the dense desktop
 * Header is hidden below md (see Header.tsx). Brand wordmark left, a 44px
 * search action right that routes to /discover.
 */
export function MobileHeader() {
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-30 md:hidden h-14 bg-bg/70 backdrop-blur-xl backdrop-saturate-150 border-b border-border flex items-center px-4">
      <Link
        to="/"
        className="font-display text-xl text-amber tracking-tight flex items-center gap-2.5 -tracking-[0.01em] rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        aria-label="Bingery — home"
      >
        <span
          aria-hidden
          className="inline-block w-2 h-2 rounded-full bg-amber shadow-[0_0_12px_rgba(239,171,129,0.7)]"
        />
        Bingery
      </Link>
      <button
        type="button"
        onClick={() => navigate("/discover")}
        aria-label="Search"
        className="ml-auto -mr-1.5 w-11 h-11 flex items-center justify-center rounded-pill text-text-muted hover:text-amber transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60"
      >
        <Search size={20} strokeWidth={1.8} />
      </button>
    </header>
  );
}
