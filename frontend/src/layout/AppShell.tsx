import { Outlet, Link } from "react-router-dom";

export default function AppShell() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="px-6 py-4 border-b border-border flex gap-4 items-center">
        <Link to="/" className="font-display text-xl text-amber">Bingery</Link>
        <nav className="flex gap-4 text-sm text-text-muted">
          <Link to="/discover">Discover</Link>
          <Link to="/watchlist">Watchlist</Link>
          <Link to="/for-you">For you</Link>
          <Link to="/chat">Chat</Link>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
