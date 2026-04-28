import { Outlet } from "react-router-dom";
import { AmbientBlobs } from "@/design/AmbientBlobs";
import { GrainOverlay } from "@/design/GrainOverlay";
import { Header } from "./Header";

export default function AppShell() {
  return (
    <div className="relative min-h-screen bg-bg text-text">
      <AmbientBlobs />
      <GrainOverlay />
      <div className="relative z-10">
        <Header />
        <main className="max-w-7xl mx-auto px-6 py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
