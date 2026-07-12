'use client';

import { useEffect } from 'react';

/**
 * Registers the service worker for every visitor so the app is installable
 * (PWA criteria) even before the user enables push notifications.
 * Re-registering the same script URL is a no-op, so this coexists with
 * usePushNotifications' own register call.
 */
export default function PwaRegister() {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* offline/unsupported — installability just won't trigger */
    });
  }, []);
  return null;
}
