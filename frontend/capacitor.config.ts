import type { CapacitorConfig } from '@capacitor/cli';

/**
 * TrueBrief native shell (Android/iOS) — Capacitor in remote-URL mode.
 *
 * The webview loads the HOSTED Next.js app (server components + Supabase
 * server-side auth need a server, so the frontend is not statically
 * exportable). `mobile-shell/` is a tiny local fallback page shown only if
 * the remote is unreachable at launch.
 *
 * Which URL the app points at is decided at `npx cap sync` time:
 *   CAP_SERVER_URL=https://<your-tunnel>.trycloudflare.com npx cap sync   (dev, phone → PC)
 *   CAP_SERVER_URL unset → PROD_URL below                                (production builds)
 *
 * allowNavigation must cover EVERY host the app legitimately navigates to, or
 * Capacitor kicks that navigation out to the system browser (which reads as
 * "the app dumped me into Chrome"). The webview itself only ever talks to
 * our own hosted frontend (`*.up.railway.app`) and the backend API — Google
 * OAuth runs in an in-app Custom Tab via @capacitor/browser instead of
 * webview navigation (see NativeGoogleButton), and email magic links are
 * opened by the user's mail client, not this webview. If a future flow needs
 * the webview to navigate to Supabase directly (e.g. `*.supabase.co`), add
 * it here — it is deliberately NOT in this list today because nothing
 * requires it.
 */

const PROD_URL = 'https://frontend-production-aa11.up.railway.app'; // ← set to the real deployed frontend URL

const config: CapacitorConfig = {
  appId: 'com.truebrief.app',
  appName: 'TrueBrief',
  webDir: 'mobile-shell',
  server: {
    url: process.env.CAP_SERVER_URL || PROD_URL,
    androidScheme: 'https',
    allowNavigation: [
      '*.up.railway.app',
    ],
  },
  android: {
    allowMixedContent: false,
  },
  plugins: {
    SplashScreen: {
      // Held open until the web app mounts and calls hide() — this is what
      // removes the white "loading a website" flash on cold start.
      launchAutoHide: false,
      backgroundColor: '#0B0F1A',
      showSpinner: false,
      androidSpinnerStyle: 'small',
      splashFullScreen: true,
      splashImmersive: false,
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0B0F1A',
      overlaysWebView: false,
    },
    Keyboard: {
      resize: 'native',
      resizeOnFullScreen: true,
    },
  },
};

export default config;
