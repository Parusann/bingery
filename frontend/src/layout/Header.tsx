import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/design/Button";
import { useAuth } from "@/stores/auth";
import { NavBar } from "./NavBar";

export function Header() {
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-30 px-6 py-3 border-b border-border/60 bg-bg/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto flex items-center gap-6">
        <Link to="/" className="font-display text-lg text-amber tracking-tight">
          Bingery
        </Link>
        <NavBar />
        <div className="ml-auto flex items-center gap-2">
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
