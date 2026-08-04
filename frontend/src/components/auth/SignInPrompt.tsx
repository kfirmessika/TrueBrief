'use client';

/**
 * Shown in place of real content on any (app) page when there's no Supabase
 * session — the app shell (Sidebar/BottomTabBar + page chrome) still renders
 * normally, only the data area swaps to this. Inline CSS-var styles to match
 * the shell/topic-page convention (see frontend CLAUDE.md "Styling split") —
 * this is shell chrome, not a generic Tailwind component, same reasoning as
 * AuthCard.
 */

import Link from 'next/link';

export function SignInPrompt({
  title = 'Sign in to start tracking',
  message = 'Track topics and see only what actually changed — sign in to get started.',
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div style={{ textAlign: 'center', padding: '80px 24px' }}>
      <p style={{ fontSize: 16, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 6px' }}>
        {title}
      </p>
      <p
        style={{
          fontSize: 13, color: 'var(--color-text-tertiary)', margin: '0 auto 20px',
          maxWidth: 320, lineHeight: 1.6,
        }}
      >
        {message}
      </p>
      <Link
        href="/sign-in"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 7,
          padding: '11px 20px', borderRadius: 10, border: 'none', cursor: 'pointer',
          background: 'var(--tb-green)', color: '#fff',
          fontSize: 14, fontWeight: 500, textDecoration: 'none', fontFamily: 'inherit',
        }}
      >
        Sign in
      </Link>
    </div>
  );
}
