'use client';

/**
 * Mobile primary navigation. Replaces the desktop Sidebar below 768px
 * (visibility is CSS-driven via .tb-mobile-only so there is no hydration flash
 * and no window-width guessing on the server).
 *
 * Sits above the OS gesture bar via env(safe-area-inset-bottom) — see globals.css.
 */

import { usePathname, useRouter } from 'next/navigation';
import { LayoutGrid, Layers, Plus, Settings } from 'lucide-react';

const TABS = [
  { href: '/dashboard', label: 'Today',    Icon: LayoutGrid },
  { href: '/topics',    label: 'Topics',   Icon: Layers },
] as const;

const TRAILING = [
  { href: '/settings',  label: 'Settings', Icon: Settings },
] as const;

export default function BottomTabBar() {
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (href: string) =>
    href === '/topics'
      ? pathname === '/topics' || (pathname.startsWith('/topics/') && pathname !== '/topics/new')
      : pathname === href;

  const tab = ({ href, label, Icon }: { href: string; label: string; Icon: typeof LayoutGrid }) => {
    const active = isActive(href);
    return (
      <button
        key={href}
        onClick={() => router.push(href)}
        aria-label={label}
        aria-current={active ? 'page' : undefined}
        style={{
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
          background: 'none', border: 'none', cursor: 'pointer', padding: '8px 0 2px',
          fontFamily: 'inherit', fontSize: 10, fontWeight: active ? 600 : 400,
          color: active ? 'var(--tb-green)' : 'var(--color-text-tertiary)',
          WebkitTapHighlightColor: 'transparent',
          transition: 'color 120ms ease',
        }}
      >
        <Icon size={21} strokeWidth={active ? 2.2 : 1.7} />
        {label}
      </button>
    );
  };

  return (
    <nav
      className="tb-mobile-only tb-bottom-tabs"
      style={{
        display: 'flex', alignItems: 'flex-end',
        borderTop: '0.5px solid var(--color-border-tertiary)',
        background: 'var(--color-background-secondary)',
        flexShrink: 0,
      }}
    >
      {TABS.map(tab)}

      {/* Elevated primary action — the one thing users do most. */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
        <button
          onClick={() => router.push('/topics/new')}
          aria-label="New topic"
          style={{
            marginTop: -16, width: 48, height: 48, borderRadius: '50%',
            background: 'var(--tb-green)', color: '#fff',
            border: '3px solid var(--color-background-secondary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', boxShadow: '0 4px 14px rgba(0,0,0,0.18)',
            WebkitTapHighlightColor: 'transparent',
          }}
        >
          <Plus size={23} strokeWidth={2.4} />
        </button>
      </div>

      {TRAILING.map(tab)}
    </nav>
  );
}
