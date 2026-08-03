'use client';

/**
 * Native-app-only "Continue with Google" — opens Supabase's OAuth URL in an
 * in-app Custom Tab (via @capacitor/browser) instead of full external
 * Chrome, then relies on the truebrief://oauth-callback custom scheme to
 * hand control back to this app.
 *
 * Why not just call signInWithOAuth() and let it redirect normally: Google
 * refuses to run inside an embedded Capacitor webview, so the OAuth hop
 * necessarily has to leave the webview. `skipBrowserRedirect: true` stops
 * the Supabase SDK from doing that navigation itself (which would just be
 * `window.location.href = url`, landing us in the webview again) — instead
 * it hands back the authorization URL as data, and we open THAT ourselves
 * with `Browser.open()`, which runs it in a Chrome Custom Tab rather than
 * dumping the user into a separate full-browser app.
 *
 * Once Google approves, Supabase redirects the Custom Tab to `redirectTo`
 * (truebrief://oauth-callback?code=...). Android's intent-filter
 * (AndroidManifest.xml) hands that custom-scheme URL straight back to this
 * app's activity, where NativeShell's `appUrlOpen` listener closes the
 * Custom Tab and forwards the URL into an in-webview navigation to
 * /sso-callback. That page calls exchangeCodeForSession(code) in the SAME
 * webview instance that started the flow, so the PKCE code_verifier
 * Supabase stashed in this webview's storage when `start()` ran below is
 * still there to complete the exchange — no shared-cookie hack needed.
 *
 * IMPORTANT: truebrief://oauth-callback must be added to the Supabase
 * Dashboard's Authentication -> URL Configuration -> Redirect URLs
 * allowlist, or Supabase silently rejects the redirect and the callback is
 * dropped. This exact class of bug (unlisted redirect URL) is what broke
 * the Clerk version of this same native flow.
 */

import { createClient } from '@/lib/supabase/client';

export default function NativeGoogleButton({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  void mode; // Supabase OAuth doesn't distinguish sign-in vs sign-up — same call either way.

  const start = async () => {
    const supabase = createClient();
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: 'truebrief://oauth-callback',
        skipBrowserRedirect: true,
      },
    });

    if (error || !data?.url) {
      console.error('Failed to start Google sign-in', error);
      return;
    }

    const { Browser } = await import('@capacitor/browser');
    await Browser.open({ url: data.url });
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
