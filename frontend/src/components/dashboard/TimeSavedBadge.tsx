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
    <div className="bg-white border border-slate-100 rounded-2xl px-4 py-2 flex items-center gap-3 shadow-sm">
      <div className="bg-green-50 p-1.5 rounded-lg">
        <Clock className="h-4 w-4 text-green-600" />
      </div>
      <div className="flex flex-col leading-tight">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          Time Saved
        </span>
        <span className="text-sm font-black text-green-600">
          {formatTimeSaved(time_saved_minutes)}
        </span>
      </div>
      <span className="text-slate-200">|</span>
      <div className="flex flex-col leading-tight">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          Articles Scanned
        </span>
        <span className="text-sm font-black text-slate-700">
          {articles_scanned.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
