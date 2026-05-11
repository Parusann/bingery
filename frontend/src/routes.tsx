import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";
import { LandingPage } from "@/features/landing/LandingPage";
import { AuthPage } from "@/features/auth/AuthPage";

const Placeholder = ({ name }: { name: string }) => (
  <div className="p-10 font-display text-3xl text-amber">{name}</div>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "discover", element: <Placeholder name="Discover" /> },
      { path: "anime/:id", element: <Placeholder name="Anime detail" /> },
      { path: "watchlist", element: <Placeholder name="Watchlist" /> },
      { path: "for-you", element: <Placeholder name="For you" /> },
      { path: "chat", element: <Placeholder name="Chat" /> },
      { path: "auth", element: <AuthPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
