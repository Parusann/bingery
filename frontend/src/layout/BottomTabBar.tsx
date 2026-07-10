import { NavLink } from "react-router-dom";
import { Compass, CalendarDays, Bookmark, Sparkles, MoreHorizontal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

const TABS: { to: string; label: string; Icon: LucideIcon }[] = [
  { to: "/discover", label: "Discover", Icon: Compass },
  { to: "/schedule", label: "Schedule", Icon: CalendarDays },
  { to: "/watchlist", label: "Watchlist", Icon: Bookmark },
  { to: "/for-you", label: "For you", Icon: Sparkles },
];

interface Props {
  onOpenMore: () => void;
  moreOpen: boolean;
}

/**
 * Fixed bottom navigation — the spine of the mobile app. Mobile-only
 * (md:hidden). 4 primary NavLinks + a More button that opens the MoreSheet.
 *
 * Active style: 2px amber top-indicator bar on the active tab.
 * (Alternative explored in design — a soft amber pill behind the active
 * icon/label: wrap the icon+label in a span and toggle
 * `bg-amber/[0.12] rounded-xl px-3 py-1` when active instead of the bar.)
 */
export function BottomTabBar({ onOpenMore, moreOpen }: Props) {
  const base =
    "relative flex-1 flex flex-col items-center justify-center gap-1 min-h-[56px] py-2 " +
    "text-[10px] font-mono tracking-wide transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-inset";

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 md:hidden bg-bg/80 backdrop-blur-xl border-t border-border"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="flex">
        {TABS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(base, isActive ? "text-amber" : "text-text-muted hover:text-text")
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute top-0 h-[2px] w-8 rounded-full bg-amber shadow-[0_0_10px_rgba(239,171,129,0.8)]" />
                )}
                <Icon size={22} strokeWidth={isActive ? 2 : 1.8} />
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}

        <button
          type="button"
          onClick={onOpenMore}
          aria-label="More"
          className={cn(base, moreOpen ? "text-amber" : "text-text-muted hover:text-text")}
        >
          {moreOpen && (
            <span className="absolute top-0 h-[2px] w-8 rounded-full bg-amber shadow-[0_0_10px_rgba(239,171,129,0.8)]" />
          )}
          <MoreHorizontal size={22} strokeWidth={1.8} />
          <span>More</span>
        </button>
      </div>
    </nav>
  );
}
