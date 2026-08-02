'use client';

/**
 * Native-app-only "Continue with Google" — replaces Clerk's built-in button
 * (hidden on native, see sign-in/sign-up pages) with one that redirects to
 * truebrief://oauth-callback instead of an https /sso-callback route.
 *
 * Why a custom scheme: Google refuses to run inside an embedded webview, so
 * this hop necessarily leaves the app (Capacitor auto-launches it externally
 * since accounts.google.com isn't in allowNavigation). Once Google approves,
 * Clerk's backend does the token exchange server-side and needs somewhere to
 * send the browser to complete the ticket exchange — pointing that at a
 * normal https URL would run it in whatever external browser context the OS
 * opened, with no way to get the resulting session back into the app.
 * Pointing it at our own custom scheme instead makes Android hand that
 * redirect straight back to this app (see AndroidManifest's intent-filter),
 * where NativeShell's appUrlOpen listener forwards it into an in-webview
 * navigation to /sso-callback — completing the exchange in the app's own
 * cookie jar via Clerk's one-time ticket, not a shared-cookie hack.
 *
 * API shape verified against the installed @clerk/shared type defs directly
 * (SignInFutureSSOParams / SignInSignalValue) rather than docs, which
 * describe an older, differently-shaped authenticateWithRedirect() API this
 * package version doesn't expose:
 *   - redirectCallbackUrl: where the actual ticket exchange happens — must
 *     be the custom scheme.
 *   - redirectUrl: the in-app destination AFTER that exchange completes.
 */

import { useSignIn, useSignUp } from '@clerk/nextjs';

export default function NativeGoogleButton({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const { signIn } = useSignIn();
  const { signUp } = useSignUp();

  const start = async () => {
    const params = {
      strategy: 'oauth_google' as const,
      redirectCallbackUrl: 'truebrief://oauth-callback',
      redirectUrl: '/dashboard',
    };
    if (mode === 'sign-in') await signIn.sso(params);
    else await signUp.sso(params);
  };

  return (
    <button
      type="button"
      onClick={start}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
        width: '100%', padding: '10px 16px', marginBottom: 16,
        border: '1px solid #d1d5db', borderRadius: 8,
        background: '#fff', color: '#1f2937',
        fontFamily: 'inherit', fontSize: 14, fontWeight: 500, cursor: 'pointer',
      }}
    >
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.88 2.7-6.62z" />
        <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.81.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18z" />
        <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z" />
        <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z" />
      </svg>
      Continue with Google
    </button>
  );
}
