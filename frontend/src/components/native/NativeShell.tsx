'use client';

/**
 * Native runtime wiring for the Capacitor shell (Android/iOS).
 *
 * Mounted once in the root layout. On the web this is a no-op — every Capacitor
 * import is dynamic and guarded by isNativePlatform(), so the browser bundle
 * never pays for it and SSR never touches a native API.
 *
 * What it fixes (the things that made the app feel like "a website in a box"):
 *  - white flash on cold start        → splash held until React mounts, then hidden
 *  - status bar clashing with the UI  → dark style, app-colored, not overlaying
 *  - hardware Back quitting the app   → walks in-app history first, exits only at root
 *  - Google sign-in stuck in Chrome   → truebrief://oauth-callback forwarded back in-webview
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function NativeShell() {
  const router = useRouter();

  useEffect(() => {
    let disposed = false;
    const cleanups: Array<() => void> = [];

    (async () => {
      const { Capacitor } = await import('@capacitor/core');
      if (!Capacitor.isNativePlatform() || disposed) return;

      // Status bar: match the app chrome instead of the default black-on-white.
      try {
        const { StatusBar, Style } = await import('@capacitor/status-bar');
        await StatusBar.setStyle({ style: Style.Dark });
        if (Capacitor.getPlatform() === 'android') {
          await StatusBar.setBackgroundColor({ color: '#0B0F1A' });
          await StatusBar.setOverlaysWebView({ overlay: false });
        }
      } catch {
        /* status bar is cosmetic — never block startup on it */
      }

      // Hardware back button: in-app history first, quit only from a root tab.
      try {
        const { App } = await import('@capacitor/app');
        const handle = await App.addListener('backButton', ({ canGoBack }) => {
          const atRoot = ['/dashboard', '/topics', '/settings'].includes(
            window.location.pathname,
          );
          if (canGoBack && !atRoot) router.back();
          else App.exitApp();
        });
        cleanups.push(() => { void handle.remove(); });
      } catch {
        /* fall through to default OS behaviour */
      }

      // Google OAuth completion: Android hands the browser's final redirect
      // (truebrief://oauth-callback?<Clerk ticket>) to this activity. Forward
      // the query string into an in-webview navigation to /sso-callback so
      // Clerk.js completes the exchange using the APP's own cookie jar, not
      // whatever browser context Google's login ran in.
      try {
        const { App } = await import('@capacitor/app');
        const handle = await App.addListener('appUrlOpen', ({ url }) => {
          const parsed = new URL(url);
          if (parsed.protocol === 'truebrief:' && parsed.hostname === 'oauth-callback') {
            window.location.href = `/sso-callback${parsed.search}`;
          }
        });
        cleanups.push(() => { void handle.remove(); });
      } catch {
        /* if this fails, Google sign-in falls back to being stuck in the browser */
      }

      // Splash last: only drop it once the shell above is actually configured.
      try {
        const { SplashScreen } = await import('@capacitor/splash-screen');
        await SplashScreen.hide();
      } catch {
        /* if the plugin is missing the splash auto-hides anyway */
      }
    })();

    return () => {
      disposed = true;
      cleanups.forEach(fn => fn());
    };
  }, [router]);

  return null;
}
