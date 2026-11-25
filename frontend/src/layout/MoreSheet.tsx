import { ArrowUpRight, UserCheck } from "lucide-react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Modal } from "@/design/Modal";
import { useAuth } from "@/stores/auth";
import { useNsfw } from "@/stores/nsfw";
import { NsfwToggle } from "./NsfwToggle";
import { morePages } from "./navigation";

export function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const visible = useNsfw((s) => s.visible);
  const { pathname, search, hash } = useLocation();
  const pages = user?.is_owner
    ? [...morePages, { to: "/admin/waitlist", label: "Waitlist", Icon: UserCheck }]
    : morePages;
  return (
    <Modal open={open} onClose={onClose} label="More" maxWidth="490px">
      <div className="px-5 pb-6 pt-3 md:p-7">
        <h2 className="font-display text-3xl mb-5">More from Bingery</h2>
        <nav aria-label="More destinations" className="more-links">
          {pages.map(({ to, label, Icon }) => (
            <NavLink to={to} key={to} onClick={onClose}>
              <Icon size={18} aria-hidden />{label}<ArrowUpRight className="ml-auto opacity-50" size={13} aria-hidden />
            </NavLink>
          ))}
        </nav>
        <div className="mt-5 flex items-center gap-3 border-t border-border pt-4">
          <NsfwToggle size="lg" />
          <span className="flex-1 text-sm">Ecchi content</span>
          <span className="text-sm text-text-muted">{visible ? "Visible" : "Hidden"}</span>
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-border pt-4 text-sm">
          <span className="truncate text-text-muted">{user ? (user.display_name || user.username) : "Guest account"}</span>
          {user ? <button type="button" onClick={() => { signOut(); onClose(); }} className="nav-signin">Sign out</button>
            : <Link to="/auth" state={{ returnTo: ["/","/auth"].includes(pathname) ? "/discover" : pathname + search + hash }} onClick={onClose} className="nav-signin">Sign in</Link>}
        </div>
      </div>
    </Modal>
  );
}
