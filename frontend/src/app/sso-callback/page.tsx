'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';

/**
 * Completes both the normal web OAuth/magic-link flow (Supabase/Google
 * redirect here directly with ?code=...) AND the native-app flow
 * (NativeShell's appUrlOpen listener forwards the custom-scheme callback
 * here via an in-webview navigation, once Android hands the browser's
 * redirect back to the app). Either way this page loads with a PKCE `code`
 * in the query string, and exchangeCodeForSession() swaps it for a session
 * using whichever storage this page happens to be running in — the app's
 * own webview localStorage, when reached via the native flow (see
 * NativeGoogleButton for why that's the same storage the flow started in).
 *
 * Reads the query string via window.location instead of useSearchParams()
 * to avoid the Suspense-boundary requirement useSearchParams imposes on
 * static builds — this page is inherently client-only/dynamic anyway.
 */
export default function SsoCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get('code');
    if (!code) {
      setError('Missing authorization code.');
      return;
    }

    const supabase = createClient();
    supabase.auth.exchangeCodeForSession(code).then(({ error: exchangeError }) => {
      if (exchangeError) {
        setError(exchangeError.message);
        return;
      }
      router.replace('/dashboard');
    });
  }, [router]);

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--color-background-secondary)', padding: 16,
      }}
    >
      {error ? (
        <p style={{ fontSize: 13, color: '#B45309', textAlign: 'center' }}>
          Sign-in failed: {error}
        </p>
      ) : (
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>Signing in…</p>
      )}
    </div>
  );
}
