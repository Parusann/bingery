import { Activity, BarChart3, Bookmark, CalendarDays, Compass, Leaf, Library, MessageCircle, Scale, Sparkles } from "lucide-react";

export const primaryPages = [
  { to: "/discover", label: "Discover", Icon: Compass },
  { to: "/schedule", label: "Schedule", Icon: CalendarDays },
  { to: "/watchlist", label: "Watchlist", Icon: Bookmark },
  { to: "/for-you", label: "For you", Icon: Sparkles },
];

export const morePages = [
  { to: "/seasonal", label: "Seasonal", Icon: Leaf },
  { to: "/collections", label: "Collections", Icon: Library },
  { to: "/chat", label: "AI guide", Icon: MessageCircle },
  { to: "/compare", label: "Compare", Icon: Scale },
  { to: "/stats", label: "Stats", Icon: BarChart3 },
  { to: "/activity", label: "Activity", Icon: Activity },
];

export function isMorePage(path: string) {
  return path.startsWith("/admin/") || morePages.some(({ to }) => path === to || path.startsWith(to + "/"));
}
