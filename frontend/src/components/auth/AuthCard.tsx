'use client';

/**
 * Custom sign-in / sign-up card, replacing Clerk's hosted <SignIn>/<SignUp>
 * widgets. Styled with inline CSS-var styles to match the app shell
 * (Sidebar, settings page) rather than Tailwind — this card is effectively
 * shell chrome, not a generic reusable widget.
 *
 * Two auth paths:
 *  - Google OAuth: web calls signInWithOAuth() directly (Supabase redirects
 *    the browser to /sso-callback itself); native renders NativeGoogleButton
 *    instead, which opens an in-app Custom Tab — see that file for why.
 *  - Email: signInWithOtp() sends a magic link (shouldCreateUser defaults to
 *    true, so this single flow covers both sign-in and sign-up — no
 *    password to manage).
 */

import { useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useIsNativeApp } from '@/hooks/useIsNativeApp';
import NativeGoogleButton from '@/components/native/NativeGoogleButton';

const googleButtonStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
  width: '100%', padding: '10px 16px',
  border: '1px solid #d1d5db', borderRadius: 8,
  background: '#fff', color: '#1f2937',
  fontFamily: 'inherit', fontSize: 14, fontWeight: 500, cursor: 'pointer',
};

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.9c1.7-1.57 2.7-3.88 2.7-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.9-2.26c-.81.54-1.84.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.95 10.7A5.4 5.4 0 0 1 3.67 9c0-.59.1-1.17.28-1.7V4.97H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.97l2.99 2.33C4.66 5.17 6.65 3.58 9 3.58z" />
    </svg>
  );
}

export function AuthCard({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const isNativeApp = useIsNativeApp();
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [error, setError] = useState('');

  const title = mode === 'sign-in' ? 'Sign in to TrueBrief' : 'Create your account';
  const subtitle = mode === 'sign-in'
    ? 'Welcome back — get only the delta, never the same news twice.'
    : 'Track a topic once. Only see what actually changed since last time.';

  const handleGoogle = async () => {
    setError('');
    const supabase = createClient();
    const { data, error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/sso-callback`,
      },
    });
    if (oauthError) {
      setError(oauthError.message);
      return;
    }
    if (data?.url) window.location.href = data.url;
  };

  const handleEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setStatus('sending');
    setError('');
    const supabase = createClient();
    const { error: otpError } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        emailRedirectTo: `${window.location.origin}/sso-callback`,
      },
    });
    if (otpError) {
      setError(otpError.message);
      setStatus('error');
      return;
    }
    setStatus('sent');
  };

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
          <button type="button" onClick={handleGoogle} style={googleButtonStyle}>
            <GoogleIcon />
            Continue with Google
          </button>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0' }}>
          <div style={{ flex: 1, height: 1, background: 'var(--color-border-tertiary)' }} />
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>or</span>
          <div style={{ flex: 1, height: 1, background: 'var(--color-border-tertiary)' }} />
        </div>

        {status === 'sent' ? (
          <div style={{
            fontSize: 13, color: 'var(--tb-green-dark)', background: 'var(--tb-green-light)',
            border: '0.5px solid var(--tb-green-border)', borderRadius: 8,
            padding: '10px 12px', lineHeight: 1.5,
          }}>
            Check <strong>{email}</strong> for a sign-in link.
          </div>
        ) : (
          <form onSubmit={handleEmail} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              style={{
                fontSize: 13, padding: '9px 12px', borderRadius: 8,
                border: '0.5px solid var(--color-border-secondary)',
                background: 'var(--color-background-primary)', color: 'var(--color-text-primary)',
                fontFamily: 'inherit', outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={status === 'sending'}
              style={{
                fontSize: 13, fontWeight: 500, padding: '10px 12px', borderRadius: 8,
                border: 'none', cursor: status === 'sending' ? 'default' : 'pointer',
                background: 'var(--tb-green)', color: '#fff', fontFamily: 'inherit',
                opacity: status === 'sending' ? 0.7 : 1,
              }}
            >
              {status === 'sending' ? 'Sending…' : 'Continue with email'}
            </button>
          </form>
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
