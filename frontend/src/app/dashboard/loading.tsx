import { SkeletonCard } from '@/components/ui/Skeleton';

export default function DashboardLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
      {/* Header skeleton */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="space-y-2">
          <div className="h-9 w-40 rounded-lg bg-[var(--color-surface-overlay)] animate-pulse" />
          <div className="h-4 w-56 rounded bg-[var(--color-surface-overlay)] animate-pulse" />
        </div>
        <div className="h-10 w-48 rounded-xl bg-[var(--color-surface-overlay)] animate-pulse" />
      </div>

      {/* Add form skeleton */}
      <div className="h-14 max-w-4xl rounded-xl bg-[var(--color-surface-overlay)] animate-pulse" />

      {/* Topic cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[0, 1, 2].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}
