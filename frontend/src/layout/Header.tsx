import { Clapperboard, Search } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/stores/auth";
import { NavBar, type NavigationProps } from "./NavBar";
import { NsfwToggle } from "./NsfwToggle";

export function Header(props: NavigationProps) {
  const user = useAuth((s) => s.user);
  const { pathname, search, hash } = useLocation();
  return (
    <header className="site-header">
      <div className="mx-auto flex h-14 md:h-16 max-w-7xl items-center gap-4 lg:gap-10 px-4 md:px-6">
        <Link to="/" aria-label="Bingery — home" className="brand-wordmark">
          <span className="brand-mark"><Clapperboard size={21} strokeWidth={2} aria-hidden /></span>
          Bingery
        </Link>
        <NavBar {...props} />
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden md:block"><NsfwToggle /></div>
          <Link
            to={pathname === "/discover" ? { pathname, search, hash: "#catalog-search" } : "/discover#catalog-search"}
            onClick={() => { if (pathname === "/discover") document.getElementById("catalog-search")?.focus(); }}
            aria-label="Search catalog"
            className="md:hidden p-2 text-text-muted"
          >
            <Search size={20} aria-hidden />
          </Link>
          {user ? (
            <button type="button" className="account-avatar" onClick={props.onOpenMore}
              aria-label="Account menu" aria-haspopup="dialog" aria-expanded={props.moreOpen}
              title={user.display_name || user.username}>
              {(user.display_name || user.username).slice(0, 1).toUpperCase()}
            </button>
          ) : pathname !== "/auth" && (
            <Link to="/auth" state={{ returnTo: pathname === "/" ? "/discover" : pathname + search + hash }} className="nav-signin">Sign in</Link>
          )}
        </div>
      </div>
    </header>
  );
}
