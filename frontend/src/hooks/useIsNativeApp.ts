'use client';

/**
 * `true`/`false` only inside/outside the Capacitor native shell; `null` while
 * still checking (one microtask on mount — Capacitor.isNativePlatform() needs
 * the dynamic import to resolve first).
 *
 * The null state matters: Clerk's <SignIn>/<SignUp> mount their internal
 * widget once and do NOT react to the `appearance` prop changing afterwards.
 * Rendering with appearance=undefined first, then flipping it once
 * isNativeApp resolves, does nothing — Google sign-in stays visible even in
 * the app. Callers must wait for non-null before mounting Clerk components
 * (see sign-in/sign-up pages) so Clerk only ever mounts once, correctly.
 */

import { useEffect, useState } from 'react';

export function useIsNativeApp(): boolean | null {
  const [isNative, setIsNative] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    import('@capacitor/core').then(({ Capacitor }) => {
      if (!cancelled) setIsNative(Capacitor.isNativePlatform());
    });
    return () => { cancelled = true; };
  }, []);

  return isNative;
}
