import { NavLink, useLocation } from "react-router-dom";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/cn";
import { isMorePage, primaryPages } from "./navigation";
import type { NavigationProps } from "./NavBar";

export function BottomTabBar({ onOpenMore, moreOpen }: NavigationProps) {
  const { pathname } = useLocation();
  const base =
    "relative flex-1 flex flex-col items-center justify-center gap-1 min-h-[56px] py-2 " +
    "text-[10px] font-mono tracking-wide transition-colors " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-inset";

  return (
    <nav aria-label="Main navigation"
      className="fixed inset-x-0 bottom-0 z-40 md:hidden bg-bg/80 backdrop-blur-xl border-t border-border"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="flex">
        {primaryPages.map(({ to, label, Icon }) => (
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
          aria-expanded={moreOpen} aria-haspopup="dialog"
          className={cn(base, moreOpen || isMorePage(pathname) ? "text-amber" : "text-text-muted hover:text-text")}
        >
          {(moreOpen || isMorePage(pathname)) && (
            <span className="absolute top-0 h-[2px] w-8 rounded-full bg-amber shadow-[0_0_10px_rgba(239,171,129,0.8)]" />
          )}
          <MoreHorizontal size={22} strokeWidth={1.8} />
          <span>More</span>
        </button>
      </div>
    </nav>
  );
}
