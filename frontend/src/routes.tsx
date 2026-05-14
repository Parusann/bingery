import { Suspense, lazy } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";
import { RouteSkeleton } from "@/layout/RouteSkeleton";
import { LandingPage } from "@/features/landing/LandingPage";

const AuthPage = lazy(() =>
  import("@/features/auth/AuthPage").then((m) => ({ default: m.AuthPage }))
);
const DiscoverPage = lazy(() =>
  import("@/features/discover/DiscoverPage").then((m) => ({ default: m.DiscoverPage }))
);
const AnimeDetailPage = lazy(() =>
  import("@/features/details/AnimeDetailPage").then((m) => ({ default: m.AnimeDetailPage }))
);
const WatchlistPage = lazy(() =>
  import("@/features/watchlist/WatchlistPage").then((m) => ({ default: m.WatchlistPage }))
);
const ForYouPage = lazy(() =>
  import("@/features/for-you/ForYouPage").then((m) => ({ default: m.ForYouPage }))
);
const ChatPage = lazy(() =>
  import("@/features/chat/ChatPage").then((m) => ({ default: m.ChatPage }))
);
const CollectionsListPage = lazy(() =>
  import("@/features/collections/CollectionsListPage").then((m) => ({
    default: m.CollectionsListPage,
  }))
);
const CollectionDetailPage = lazy(() =>
  import("@/features/collections/CollectionDetailPage").then((m) => ({
    default: m.CollectionDetailPage,
  }))
);
const StatsPage = lazy(() =>
  import("@/features/stats/StatsPage").then((m) => ({ default: m.StatsPage }))
);
const SeasonalPage = lazy(() =>
  import("@/features/seasonal/SeasonalPage").then((m) => ({ default: m.SeasonalPage }))
);
const ActivityPage = lazy(() =>
  import("@/features/activity/ActivityPage").then((m) => ({ default: m.ActivityPage }))
);
const ComparePage = lazy(() =>
  import("@/features/compare/ComparePage").then((m) => ({ default: m.ComparePage }))
);
const SchedulePage = lazy(() =>
  import("@/features/schedule/SchedulePage").then((m) => ({ default: m.SchedulePage }))
);

const withSuspense = (node: React.ReactNode) => (
  <Suspense fallback={<RouteSkeleton />}>{node}</Suspense>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "auth", element: withSuspense(<AuthPage />) },
      { path: "discover", element: withSuspense(<DiscoverPage />) },
      { path: "anime/:id", element: withSuspense(<AnimeDetailPage />) },
      { path: "watchlist", element: withSuspense(<WatchlistPage />) },
      { path: "for-you", element: withSuspense(<ForYouPage />) },
      { path: "chat", element: withSuspense(<ChatPage />) },
      { path: "collections", element: withSuspense(<CollectionsListPage />) },
      { path: "collections/:id", element: withSuspense(<CollectionDetailPage />) },
      { path: "stats", element: withSuspense(<StatsPage />) },
      { path: "seasonal", element: withSuspense(<SeasonalPage />) },
      { path: "activity", element: withSuspense(<ActivityPage />) },
      { path: "compare", element: withSuspense(<ComparePage />) },
      { path: "schedule", element: withSuspense(<SchedulePage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
