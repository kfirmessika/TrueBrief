import { SkeletonBriefRow } from '@/components/ui/Skeleton';

export default function HistoryLoading() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="space-y-2 mb-12">
        <div className="h-9 w-48 rounded-lg bg-[var(--color-surface-overlay)] animate-pulse" />
        <div className="h-4 w-72 rounded bg-[var(--color-surface-overlay)] animate-pulse" />
      </div>

      <div className="space-y-10">
        {[0, 1].map((section) => (
          <section key={section}>
            <div className="h-5 w-32 rounded bg-[var(--color-surface-overlay)] animate-pulse mb-4" />
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] divide-y divide-[var(--color-border)]">
              {[0, 1, 2].map((i) => (
                <div key={i} className="px-5 py-4">
                  <SkeletonBriefRow />
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
