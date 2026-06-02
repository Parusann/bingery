import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";
import { NavBar } from "./NavBar";
import { NsfwToggle } from "./NsfwToggle";

// NOTE: the local NsfwToggle has been extracted to ./NsfwToggle.tsx so the
// MoreSheet can reuse it. The desktop instance below renders it at size="sm"
// (36px) so this header is byte-identical to before.

export function Header() {
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const navigate = useNavigate();
  return (
    // Only change to the desktop header: `hidden md:block` so it disappears
    // below md (the MobileHeader replaces it). Inner markup is untouched.
    <header className="hidden md:block sticky top-0 z-30 px-6 py-3 border-b border-border/60 bg-bg/70 backdrop-blur-xl backdrop-saturate-150">
      <div className="max-w-7xl mx-auto flex items-center gap-8">
        <Link
          to="/"
          className="font-display text-2xl text-amber tracking-tight flex items-center gap-2.5 -tracking-[0.01em]"
          aria-label="Bingery — home"
        >
          <span
            aria-hidden
            className="inline-block w-2 h-2 rounded-full bg-amber shadow-[0_0_12px_rgba(244,182,144,0.7)]"
          />
          Bingery
        </Link>
        <NavBar />
        <div className="ml-auto flex items-center gap-2">
          <NsfwToggle size="sm" />
          {user ? (
            <>
              <span className="hidden md:inline text-sm text-text-muted">
                {user.display_name ?? user.username}
              </span>
              <Button variant="ghost" size="sm" onClick={signOut}>
                Sign out
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => navigate("/auth")}>
              Sign in
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
