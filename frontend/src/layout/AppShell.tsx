import { useState } from "react";
import { AmbientBlobs } from "@/design/AmbientBlobs";
import { GrainOverlay } from "@/design/GrainOverlay";
import { Header } from "./Header";
import { MobileHeader } from "./MobileHeader";
import { BottomTabBar } from "./BottomTabBar";
import { MoreSheet } from "./MoreSheet";
import { PageTransition } from "./PageTransition";

export default function AppShell() {
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <div className="relative min-h-screen bg-bg text-text">
      <AmbientBlobs />
      <GrainOverlay />
      <div className="relative z-10">
        <Header />        {/* desktop-only after Header gets `hidden md:block` */}
        <MobileHeader />  {/* md:hidden */}
        {/* px-4 py-5 pb-24 = mobile; md: re-pins the original px-6 py-10 */}
        <main className="max-w-7xl mx-auto px-4 py-5 pb-24 md:px-6 md:py-10 md:pb-10">
          <PageTransition />
        </main>
        <BottomTabBar onOpenMore={() => setMoreOpen(true)} moreOpen={moreOpen} />
        <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} />
      </div>
    </div>
  );
}
