import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";
import { NavBar } from "./NavBar";
import { NsfwToggle } from "./NsfwToggle";

// Desktop-only app bar (hidden below md — MobileHeader takes over). The
// wordmark is the one place the amber accent appears as "brand" rather than
// interaction; its glow uses the current amber (#efab81).

export function Header() {
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const navigate = useNavigate();
  return (
    <header className="hidden md:block sticky top-0 z-30 px-6 py-3 border-b border-border/60 bg-bg/70 backdrop-blur-xl backdrop-saturate-150">
      <div className="max-w-7xl mx-auto flex items-center gap-8">
        <Link
          to="/"
          className="font-display text-2xl text-amber tracking-tight flex items-center gap-2.5 -tracking-[0.01em] rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/60 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          aria-label="Bingery — home"
        >
          <span
            aria-hidden
            className="inline-block w-2 h-2 rounded-full bg-amber shadow-[0_0_12px_rgba(239,171,129,0.7)]"
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
