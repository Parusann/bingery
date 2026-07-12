import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";
import { useAuth } from "@/stores/auth";

const items = [
  { to: "/discover", label: "Discover" },
  { to: "/seasonal", label: "Seasonal" },
  { to: "/schedule", label: "Schedule" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/collections", label: "Collections" },
  { to: "/for-you", label: "For you" },
  { to: "/stats", label: "Stats" },
  { to: "/activity", label: "Activity" },
  { to: "/compare", label: "Compare" },
  { to: "/chat", label: "Chat" },
];

export function NavBar() {
  // Owner-only destinations (the backend enforces authorization regardless).
  const isOwner = useAuth((s) => !!s.user?.is_owner);
  const navItems = isOwner
    ? [...items, { to: "/admin/waitlist", label: "Waitlist" }]
    : items;
  return (
    <nav className="flex items-center gap-1 text-sm overflow-x-auto scrollbar-none">
      {navItems.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          className={({ isActive }) =>
            cn(
              "shrink-0 relative inline-flex items-center min-h-[44px] px-3 py-2.5 rounded-md text-text-muted transition-colors",
              "hover:text-text hover:bg-surface",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber/60",
              isActive && "text-text bg-surface-strong"
            )
          }
        >
          {it.label}
        </NavLink>
      ))}
    </nav>
  );
}
