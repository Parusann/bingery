import { Skeleton } from "@/design/Skeleton";

// Route-level fallback. Mirrors the standard page anatomy every screen now
// shares: mono eyebrow + display title, then a poster grid whose cells match
// AnimeGrid's skeletons (poster + two text lines).
export function RouteSkeleton() {
  return (
    <div>
      <div className="mb-6 space-y-2.5">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-10 w-64" rounded="md" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-x-4 gap-y-6">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="aspect-[2/3]" rounded="lg" />
            <div className="px-0.5 pt-2.5 space-y-1.5">
              <Skeleton className="h-3.5 w-11/12" />
              <Skeleton className="h-3 w-3/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
