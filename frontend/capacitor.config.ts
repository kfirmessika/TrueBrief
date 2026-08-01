import type { CapacitorConfig } from '@capacitor/cli';

/**
 * TrueBrief native shell (Android/iOS) — Capacitor in remote-URL mode.
 *
 * The webview loads the HOSTED Next.js app (server components + Clerk need a
 * server, so the frontend is not statically exportable). `mobile-shell/` is a
 * tiny local fallback page shown only if the remote is unreachable at launch.
 *
 * Which URL the app points at is decided at `npx cap sync` time:
 *   CAP_SERVER_URL=https://<your-tunnel>.trycloudflare.com npx cap sync   (dev, phone → PC)
 *   CAP_SERVER_URL unset → PROD_URL below                                (production builds)
 *
 * allowNavigation must cover EVERY host the app legitimately navigates to, or
 * Capacitor kicks that navigation out to the system browser (which reads as
 * "the app dumped me into Chrome"). Clerk uses TWO distinct hosts:
 *   <slug>.clerk.accounts.dev  — API/frontend SDK
 *   <slug>.accounts.dev        — hosted Account Portal (sign-in redirect target)
 * `*.accounts.dev` is required for the second one; `*.clerk.accounts.dev`
 * does NOT match it.
 *
 * Google OAuth blocks embedded webviews — GoogleOAuthButton opens it via
 * @capacitor/browser (system tab) instead. Email-code flow works in-app.
 */

const PROD_URL = 'https://frontend-production-aa11.up.railway.app'; // ← set to the real deployed frontend URL

const config: CapacitorConfig = {
  appId: 'com.truebrief.app',
  appName: 'TrueBrief',
  webDir: 'mobile-shell',
  server: {
    url: process.env.CAP_SERVER_URL || PROD_URL,
    androidScheme: 'https',
    // Keep Clerk's hosted auth pages inside the webview during sign-in.
    allowNavigation: [
      '*.clerk.accounts.dev',
      '*.accounts.dev',
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
