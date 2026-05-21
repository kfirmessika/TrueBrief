import type { LucideIcon } from 'lucide-react';
import { FadeIn } from './motion';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <FadeIn className={`flex flex-col items-center justify-center py-20 px-8 text-center ${className}`}>
      {Icon && (
        <div className="mb-5 rounded-2xl bg-[var(--color-surface-overlay)] p-5 border border-[var(--color-border)]">
          <Icon className="h-10 w-10 text-[var(--color-text-muted)]" strokeWidth={1.25} />
        </div>
      )}
      <h3 className="text-lg font-semibold text-[var(--color-text)] mb-2">{title}</h3>
      {description && (
        <p className="max-w-xs text-sm text-[var(--color-text-secondary)] leading-relaxed">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </FadeIn>
  );
}
