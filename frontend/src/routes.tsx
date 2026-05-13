import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";
import { LandingPage } from "@/features/landing/LandingPage";
import { AuthPage } from "@/features/auth/AuthPage";
import { DiscoverPage } from "@/features/discover/DiscoverPage";
import { AnimeDetailPage } from "@/features/details/AnimeDetailPage";
import { WatchlistPage } from "@/features/watchlist/WatchlistPage";
import { ForYouPage } from "@/features/for-you/ForYouPage";
import { ChatPage } from "@/features/chat/ChatPage";
import { CollectionsListPage } from "@/features/collections/CollectionsListPage";
import { CollectionDetailPage } from "@/features/collections/CollectionDetailPage";
import { StatsPage } from "@/features/stats/StatsPage";
import { SeasonalPage } from "@/features/seasonal/SeasonalPage";
import { ActivityPage } from "@/features/activity/ActivityPage";
import { ComparePage } from "@/features/compare/ComparePage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "auth", element: <AuthPage /> },
      { path: "discover", element: <DiscoverPage /> },
      { path: "anime/:id", element: <AnimeDetailPage /> },
      { path: "watchlist", element: <WatchlistPage /> },
      { path: "for-you", element: <ForYouPage /> },
      { path: "chat", element: <ChatPage /> },
      { path: "collections", element: <CollectionsListPage /> },
      { path: "collections/:id", element: <CollectionDetailPage /> },
      { path: "stats", element: <StatsPage /> },
      { path: "seasonal", element: <SeasonalPage /> },
      { path: "activity", element: <ActivityPage /> },
      { path: "compare", element: <ComparePage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
