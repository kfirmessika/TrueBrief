'use client';

/**
 * True only inside the Capacitor native shell (Android/iOS), never on web.
 * Starts false (matches SSR) and flips after mount — used to hide UI that
 * cannot work inside the app's webview, e.g. Google OAuth (Google blocks
 * embedded webviews by policy; there is no in-app workaround short of a
 * custom-URL-scheme deep-link flow, which isn't wired up).
 */

import { useEffect, useState } from 'react';

export function useIsNativeApp(): boolean {
  const [isNative, setIsNative] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import('@capacitor/core').then(({ Capacitor }) => {
      if (!cancelled && Capacitor.isNativePlatform()) setIsNative(true);
    });
    return () => { cancelled = true; };
  }, []);

  return isNative;
}
