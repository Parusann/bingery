import { Skeleton } from "@/design/Skeleton";

export function RouteSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-12 w-64" rounded="lg" />
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} className="aspect-[2/3]" rounded="lg" />
        ))}
      </div>
    </div>
  );
}
