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
    <FadeIn className={`flex flex-col items-center justify-center py-16 px-6 text-center ${className}`}>
      {Icon && (
        <div className="mb-4 rounded-2xl bg-[var(--color-surface-overlay)] p-4">
          <Icon className="h-8 w-8 text-[var(--color-text-muted)]" strokeWidth={1.5} />
        </div>
      )}
      <h3 className="text-base font-semibold text-[var(--color-text)]">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[var(--color-text-secondary)]">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </FadeIn>
  );
}
