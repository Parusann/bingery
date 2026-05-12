import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";
import { LandingPage } from "@/features/landing/LandingPage";
import { AuthPage } from "@/features/auth/AuthPage";
import { DiscoverPage } from "@/features/discover/DiscoverPage";
import { AnimeDetailPage } from "@/features/details/AnimeDetailPage";
import { WatchlistPage } from "@/features/watchlist/WatchlistPage";
import { ForYouPage } from "@/features/for-you/ForYouPage";
import { ChatPage } from "@/features/chat/ChatPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "discover", element: <DiscoverPage /> },
      { path: "anime/:id", element: <AnimeDetailPage /> },
      { path: "watchlist", element: <WatchlistPage /> },
      { path: "for-you", element: <ForYouPage /> },
      { path: "chat", element: <ChatPage /> },
      { path: "auth", element: <AuthPage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
