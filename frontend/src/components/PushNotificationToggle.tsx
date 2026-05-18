'use client';

import { usePushNotifications } from '@/hooks/usePushNotifications';

export default function PushNotificationToggle() {
  const { isSupported, isSubscribed, isLoading, subscribe, unsubscribe } =
    usePushNotifications();

  if (!isSupported) {
    return (
      <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-slate-50">
        <div>
          <p className="font-medium text-slate-700">Browser Notifications</p>
          <p className="text-sm text-slate-500 mt-0.5">
            Not supported in this browser.
          </p>
        </div>
        <span className="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded-full">
          Unavailable
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-white">
      <div>
        <p className="font-medium text-slate-700">Browser Notifications</p>
        <p className="text-sm text-slate-500 mt-0.5">
          {isSubscribed
            ? 'You will be notified when a new brief is ready.'
            : 'Get notified instantly when a new brief is ready.'}
        </p>
      </div>

      <button
        onClick={isSubscribed ? unsubscribe : subscribe}
        disabled={isLoading}
        className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
          isSubscribed
            ? 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm shadow-indigo-200'
        }`}
      >
        {isLoading
          ? 'Loading…'
          : isSubscribed
          ? 'Disable Notifications'
          : 'Enable Notifications'}
      </button>
    </div>
  );
}
