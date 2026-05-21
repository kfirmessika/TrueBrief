'use client';

import { usePushNotifications } from '@/hooks/usePushNotifications';

export default function PushNotificationToggle() {
  const { isSupported, isSubscribed, isLoading, subscribe, unsubscribe } = usePushNotifications();

  if (!isSupported) {
    return (
      <div className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-overlay)] px-4 py-3">
        <div>
          <p className="text-sm font-medium text-[var(--color-text)]">Browser notifications</p>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">Not supported in this browser.</p>
        </div>
        <span className="text-xs text-[var(--color-text-muted)] bg-[var(--color-surface-overlay)] px-2.5 py-1 rounded-full border border-[var(--color-border)]">
          Unavailable
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-[var(--color-text)]">Browser notifications</p>
        <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
          {isSubscribed
            ? 'You\'ll be notified when a new brief is ready.'
            : 'Get notified the moment a new brief is ready.'}
        </p>
      </div>
      <button
        onClick={isSubscribed ? unsubscribe : subscribe}
        disabled={isLoading}
        className={`shrink-0 px-4 py-2 rounded-lg text-xs font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
          isSubscribed
            ? 'bg-[var(--color-surface-overlay)] text-[var(--color-text-secondary)] hover:bg-[var(--color-border)] border border-[var(--color-border)]'
            : 'bg-[var(--color-brand)] text-white hover:bg-[var(--color-brand-dark)] shadow-sm'
        }`}
      >
        {isLoading ? 'Loading…' : isSubscribed ? 'Disable' : 'Enable'}
      </button>
    </div>
  );
}
