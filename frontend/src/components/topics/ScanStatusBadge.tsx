'use client';

import { useScanStatus } from '@/hooks/useTopics';
import { Loader2, CheckCircle2, AlertCircle, Clock } from 'lucide-react';

interface ScanStatusBadgeProps {
  taskId: string | null;
  onFinished?: () => void;
}

export function ScanStatusBadge({ taskId, onFinished }: ScanStatusBadgeProps) {
  const { data: status, isLoading } = useScanStatus(taskId);

  if (!taskId) return null;

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs font-bold text-slate-400 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-100">
        <Loader2 className="h-3 w-3 animate-spin" /> Initializing...
      </div>
    );
  }

  const state = status?.state || 'PENDING';

  const configs: Record<string, { icon: any; text: string; className: string }> = {
    PENDING: {
      icon: Clock,
      text: 'Queued',
      className: 'text-slate-500 bg-slate-100 border-slate-200',
    },
    STARTED: {
      icon: Loader2,
      text: 'Running',
      className: 'text-indigo-600 bg-indigo-50 border-indigo-100',
    },
    SUCCESS: {
      icon: CheckCircle2,
      text: 'Complete',
      className: 'text-green-600 bg-green-50 border-green-100',
    },
    FAILURE: {
      icon: AlertCircle,
      text: 'Failed',
      className: 'text-red-600 bg-red-50 border-red-100',
    },
  };

  const config = configs[state] || configs.PENDING;
  const Icon = config.icon;

  return (
    <div className={`flex items-center gap-2 text-xs font-black uppercase tracking-wider px-3 py-1.5 rounded-full border ${config.className} transition-all`}>
      <Icon className={`h-3 w-3 ${state === 'STARTED' ? 'animate-spin' : ''}`} />
      {config.text}
    </div>
  );
}
