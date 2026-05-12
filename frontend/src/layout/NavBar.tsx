import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";

const items = [
  { to: "/discover", label: "Discover" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/for-you", label: "For you" },
  { to: "/chat", label: "Chat" },
];

export function NavBar() {
  return (
    <nav className="flex items-center gap-1 text-sm">
      {items.map((it) => (
        <NavLink
          key={it.to}
          to={it.to}
          className={({ isActive }) =>
            cn(
              "relative px-3 py-1.5 rounded-md text-text-muted transition-colors",
              "hover:text-text hover:bg-white/[0.04]",
              isActive && "text-text bg-white/[0.06]"
            )
          }
        >
          {it.label}
        </NavLink>
      ))}
    </nav>
  );
}
