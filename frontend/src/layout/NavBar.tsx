import { ChevronDown } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { isMorePage, primaryPages } from "./navigation";

export interface NavigationProps {
  onOpenMore: () => void;
  moreOpen: boolean;
}

export function NavBar({ onOpenMore, moreOpen }: NavigationProps) {
  const { pathname } = useLocation();
  return (
    <nav aria-label="Main navigation" className="desktop-nav hidden md:flex">
      {primaryPages.map(({ to, label }) => <NavLink key={to} to={to}>{label}</NavLink>)}
      <button type="button" aria-haspopup="dialog" aria-expanded={moreOpen}
        data-active={isMorePage(pathname)} onClick={onOpenMore}>
        More <ChevronDown size={14} aria-hidden />
      </button>
    </nav>
  );
}
