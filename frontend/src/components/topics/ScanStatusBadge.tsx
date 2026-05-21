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
      <div className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--color-text-muted)] bg-[var(--color-surface-overlay)] px-3 py-1.5 rounded-full border border-[var(--color-border)]">
        <Loader2 className="h-3 w-3 animate-spin" /> Initializing…
      </div>
    );
  }

  const state = status?.state || 'PENDING';

  type Config = { icon: React.ElementType; text: string; color: string; bg: string };
  const configs: Record<string, Config> = {
    PENDING: { icon: Clock,         text: 'Queued',   color: 'var(--color-text-muted)',   bg: 'var(--color-surface-overlay)' },
    STARTED: { icon: Loader2,       text: 'Running',  color: 'var(--color-brand)',         bg: 'var(--color-brand-subtle)' },
    SUCCESS: { icon: CheckCircle2,  text: 'Complete', color: 'var(--color-success)',       bg: 'var(--color-success-subtle)' },
    FAILURE: { icon: AlertCircle,   text: 'Failed',   color: 'var(--color-danger)',        bg: 'var(--color-danger-subtle)' },
  };

  const cfg = configs[state] ?? configs.PENDING;
  const Icon = cfg.icon;

  return (
    <div
      className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider px-3 py-1.5 rounded-full border transition-all"
      style={{ color: cfg.color, backgroundColor: cfg.bg, borderColor: cfg.color + '33' }}
    >
      <Icon className={`h-3 w-3 ${state === 'STARTED' ? 'animate-spin' : ''}`} />
      {cfg.text}
    </div>
  );
}
