'use client';

/**
 * `true` inside the Capacitor native shell, `false` everywhere else
 * (including the brief window on mount before the dynamic import resolves —
 * callers should treat that as "assume web" rather than block rendering on
 * it, there's no auth-widget mount-once constraint here anymore).
 */

import { useEffect, useState } from 'react';

export function useIsNativeApp(): boolean {
  const [isNative, setIsNative] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import('@capacitor/core').then(({ Capacitor }) => {
      if (!cancelled) setIsNative(Capacitor.isNativePlatform());
    });
    return () => { cancelled = true; };
  }, []);

  return isNative;
}
