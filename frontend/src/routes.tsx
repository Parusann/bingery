import { Navigate, createBrowserRouter } from "react-router-dom";
import AppShell from "@/layout/AppShell";

const Placeholder = ({ name }: { name: string }) => (
  <div className="p-10 font-display text-3xl text-amber">{name}</div>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Placeholder name="Landing" /> },
      { path: "discover", element: <Placeholder name="Discover" /> },
      { path: "anime/:id", element: <Placeholder name="Anime detail" /> },
      { path: "watchlist", element: <Placeholder name="Watchlist" /> },
      { path: "for-you", element: <Placeholder name="For you" /> },
      { path: "chat", element: <Placeholder name="Chat" /> },
      { path: "auth", element: <Placeholder name="Auth" /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
