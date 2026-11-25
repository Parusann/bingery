import "./shell.css";
import { useState } from "react";
import { Outlet, ScrollRestoration } from "react-router-dom";
import { Header } from "./Header";
import { BottomTabBar } from "./BottomTabBar";
import { MoreSheet } from "./MoreSheet";

export default function AppShell() {
  const [moreOpen, setMoreOpen] = useState(false);
  const openMore = () => setMoreOpen(true);
  return (
    <div className="app-shell min-h-screen text-text">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <Header moreOpen={moreOpen} onOpenMore={openMore} />
      <main id="main-content" tabIndex={-1} className="mx-auto max-w-7xl px-4 py-5 pb-24 md:px-6 md:py-9">
        <Outlet />
      </main>
      <BottomTabBar onOpenMore={openMore} moreOpen={moreOpen} />
      <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
      <ScrollRestoration />
    </div>
  );
}
