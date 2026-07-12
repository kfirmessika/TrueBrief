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
 * Sign-in inside the webview: use Clerk's email-code flow. Google OAuth blocks
 * embedded webviews — if Google sign-in is ever needed in-app, wire the
 * @capacitor/browser plugin to open it in the system browser instead.
 */

const PROD_URL = 'https://app.truebrief.app'; // ← set to the real deployed frontend URL

const config: CapacitorConfig = {
  appId: 'com.truebrief.app',
  appName: 'TrueBrief',
  webDir: 'mobile-shell',
  server: {
    url: process.env.CAP_SERVER_URL || PROD_URL,
    androidScheme: 'https',
    // Keep Clerk's hosted auth pages inside the webview during sign-in.
    allowNavigation: ['*.clerk.accounts.dev', '*.truebrief.app'],
  },
  android: {
    allowMixedContent: false,
  },
};

export default config;
