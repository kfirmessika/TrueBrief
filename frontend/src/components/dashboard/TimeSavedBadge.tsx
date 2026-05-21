import { Clock } from 'lucide-react';
import { UserStats } from '@/lib/api';

interface TimeSavedBadgeProps {
  stats: UserStats;
}

function formatTimeSaved(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder > 0 ? `${hours}h ${remainder}m` : `${hours}h`;
}

export function TimeSavedBadge({ stats }: TimeSavedBadgeProps) {
  const { total_briefs, articles_scanned, time_saved_minutes } = stats;

  if (total_briefs === 0) return null;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2.5 shadow-sm text-sm">
      <div className="bg-[var(--color-success-subtle)] p-1.5 rounded-lg">
        <Clock className="h-3.5 w-3.5 text-[var(--color-success)]" />
      </div>
      <div className="flex items-center gap-3 divide-x divide-[var(--color-border)]">
        <div>
          <p className="text-xs text-[var(--color-text-muted)] leading-none mb-0.5">Time saved</p>
          <p className="text-sm font-bold text-[var(--color-success)]">{formatTimeSaved(time_saved_minutes)}</p>
        </div>
        <div className="pl-3">
          <p className="text-xs text-[var(--color-text-muted)] leading-none mb-0.5">Articles scanned</p>
          <p className="text-sm font-bold text-[var(--color-text)]">{articles_scanned.toLocaleString()}</p>
        </div>
      </div>
    </div>
  );
}
