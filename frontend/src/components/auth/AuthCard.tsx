'use client';

/**
 * Custom sign-in / sign-up card, replacing Clerk's hosted <SignIn>/<SignUp>
 * widgets. Styled with inline CSS-var styles to match the app shell
 * (Sidebar, settings page) rather than Tailwind — this card is effectively
 * shell chrome, not a generic reusable widget.
 *
 * Two auth paths:
 *  - Google: web uses Google Identity Services (signInWithIdToken), NOT the
 *    signInWithOAuth() redirect flow. The redirect flow bounces the browser
 *    through Supabase's own hosted callback domain, so Google's account
 *    picker literally reads "Continue to <project-ref>.supabase.co" instead
 *    of "TrueBrief" -- that's Google warning the user where they're about to
 *    be sent, and it's inherent to using Supabase's *shared* auth domain, not
 *    a config mistake (a real fix needs Supabase Custom Domains, a paid
 *    add-on, plus a domain we own -- not worth it for one transitional
 *    screen). GIS runs as a client-side popup against our own origin instead,
 *    so that screen never appears. Native still uses NativeGoogleButton's
 *    Custom Tab + signInWithOAuth, because GIS's popup doesn't work inside a
 *    Capacitor webview -- native shows the supabase.co screen until it gets
 *    a native Google Sign-In SDK integration (separate, bigger task).
 *
 * Email/password and magic-link sign-in were removed — Google is the only
 * auth path, for both sign-in and sign-up (mode only changes the copy).
 */

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { useIsNativeApp } from '@/hooks/useIsNativeApp';
import NativeGoogleButton from '@/components/native/NativeGoogleButton';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            nonce: string;
            use_fedcm_for_prompt?: boolean;
          }): void;
          renderButton(parent: HTMLElement, options: Record<string, string | number>): void;
        };
      };
    };
  }
}

/** SHA-256 hex digest, per Supabase's documented GIS nonce-hashing recipe. */
async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function AuthCard({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const isNativeApp = useIsNativeApp();
  const router = useRouter();
  const [error, setError] = useState('');
  const googleButtonRef = useRef<HTMLDivElement>(null);
  const rawNonceRef = useRef<string>('');

  const title = mode === 'sign-in' ? 'Sign in to TrueBrief' : 'Create your account';
  const subtitle = mode === 'sign-in'
    ? 'Welcome back — get only the delta, never the same news twice.'
    : 'Track a topic once. Only see what actually changed since last time.';

  useEffect(() => {
    if (isNativeApp) return; // native uses NativeGoogleButton's Custom Tab flow instead
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId) return;

    let cancelled = false;

    const setup = async () => {
      const rawNonce = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
      const hashedNonce = await sha256Hex(rawNonce);
      if (cancelled) return;
      rawNonceRef.current = rawNonce;

      const handleCredentialResponse = async (response: { credential: string }) => {
        setError('');
        const supabase = createClient();
        const { error: idTokenError } = await supabase.auth.signInWithIdToken({
          provider: 'google',
          token: response.credential,
          nonce: rawNonceRef.current,
        });
        if (idTokenError) {
          setError(idTokenError.message);
          return;
        }
        router.replace('/dashboard');
      };

      window.google?.accounts.id.initialize({
        client_id: clientId,
        callback: handleCredentialResponse,
        nonce: hashedNonce,
        use_fedcm_for_prompt: true,
      });
      if (googleButtonRef.current) {
        // Google's button takes a fixed pixel width, not a CSS one — measure the
        // actual container instead of hardcoding a desktop-sized value, or narrow
        // viewports (this card is ~285px wide at 375px, ~230px at 320px) overflow.
        // Google's own docs bound this to roughly 200-400px, so clamp into that range.
        const containerWidth = googleButtonRef.current.offsetWidth || 332;
        const buttonWidth = Math.min(400, Math.max(200, containerWidth));
        window.google?.accounts.id.renderButton(googleButtonRef.current, {
          type: 'standard', theme: 'outline', size: 'large', text: 'continue_with',
          shape: 'rectangular', logo_alignment: 'left', width: buttonWidth,
        });
      }
    };

    if (window.google) {
      setup();
    } else {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => { if (!cancelled) setup(); };
      document.head.appendChild(script);
    }

    return () => { cancelled = true; };
  }, [isNativeApp, router]);

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--color-background-secondary)', padding: 16,
      }}
    >
      <div
        style={{
          width: '100%', maxWidth: 380,
          background: 'var(--color-background-primary)',
          border: '0.5px solid var(--color-border-tertiary)',
          borderRadius: 12, padding: '32px 28px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
          <div style={{
            width: 26, height: 26, background: 'var(--tb-green)', borderRadius: 6,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: 11, fontWeight: 500, flexShrink: 0,
          }}>
            TB
          </div>
          <span style={{ fontWeight: 500, fontSize: 14, color: 'var(--color-text-primary)' }}>TrueBrief</span>
        </div>

        <p style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
          {title}
        </p>
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', margin: '0 0 24px', lineHeight: 1.5 }}>
          {subtitle}
        </p>

        {isNativeApp ? (
          <NativeGoogleButton mode={mode} />
        ) : (
          <div ref={googleButtonRef} style={{ display: 'flex', justifyContent: 'center', minHeight: 40, maxWidth: '100%', overflow: 'hidden' }} />
        )}

        {error && (
          <p style={{ fontSize: 12, color: '#B45309', margin: '10px 0 0' }}>{error}</p>
        )}

        <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '20px 0 0', textAlign: 'center' }}>
          {mode === 'sign-in' ? (
            <>New here? <a href="/sign-up" style={{ color: 'var(--tb-green)', textDecoration: 'none', fontWeight: 500 }}>Create an account</a></>
          ) : (
            <>Already have an account? <a href="/sign-in" style={{ color: 'var(--tb-green)', textDecoration: 'none', fontWeight: 500 }}>Sign in</a></>
          )}
        </p>
      </div>
    </div>
  );
}
