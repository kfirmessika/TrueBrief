'use client';

import { AuthenticateWithRedirectCallback } from "@clerk/nextjs";

/**
 * Completes both the normal web OAuth flow (Google redirects here directly)
 * AND the native-app flow (NativeShell's appUrlOpen listener forwards the
 * custom-scheme callback here via an in-webview navigation, once Android
 * hands the browser's redirect back to the app). Either way this page is
 * loaded with Clerk's one-time ticket in the query string, and
 * <AuthenticateWithRedirectCallback /> exchanges it for a session using
 * whichever cookie jar this page happens to be running in — the app's, when
 * reached via the native flow.
 */
export default function SsoCallbackPage() {
  return <AuthenticateWithRedirectCallback signInFallbackRedirectUrl="/dashboard" signUpFallbackRedirectUrl="/dashboard" />;
}
