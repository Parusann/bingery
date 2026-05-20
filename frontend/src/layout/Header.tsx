import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";
import { useNsfw } from "@/stores/nsfw";
import { NavBar } from "./NavBar";

function NsfwToggle() {
  const visible = useNsfw((s) => s.visible);
  const toggle = useNsfw((s) => s.toggle);
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={visible}
      aria-label={visible ? "Hide Ecchi content" : "Show Ecchi content"}
      title={
        visible
          ? "Ecchi visible — click to hide. (Hentai is always hidden.)"
          : "Ecchi hidden — click to show. (Hentai is always hidden.)"
      }
      className="w-9 h-9 rounded-pill border border-amber/30 bg-white/[0.04] backdrop-blur-md text-text-muted hover:text-amber hover:border-amber/55 hover:bg-amber/[0.08] transition-colors flex items-center justify-center"
    >
      {visible ? (
        // eye-open
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      ) : (
        // eye-closed
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-6.5 0-10-7-10-7a19.83 19.83 0 0 1 4.06-4.94" />
          <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c6.5 0 10 7 10 7a19.81 19.81 0 0 1-3.17 4.19" />
          <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
          <line x1="2" y1="2" x2="22" y2="22" />
        </svg>
      )}
    </button>
  );
}

export function Header() {
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-30 px-6 py-3 border-b border-border/60 bg-bg/70 backdrop-blur-xl backdrop-saturate-150">
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
          <NsfwToggle />
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
