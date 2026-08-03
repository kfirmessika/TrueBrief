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
  { href: '/dashboard',  label: 'Today',    Icon: LayoutGrid },
  { href: '/topics',     label: 'Topics',   Icon: Layers },
  { href: '/topics/new', label: 'New',      Icon: Plus },
  { href: '/settings',   label: 'Settings', Icon: Settings },
] as const;

export default function BottomTabBar() {
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (href: string) => {
    if (href === '/topics') return pathname === '/topics' || (pathname.startsWith('/topics/') && pathname !== '/topics/new');
    return pathname === href;
  };

  return (
    <nav
      className="tb-mobile-only tb-bottom-tabs"
      style={{
        // NO `display` here on purpose: an inline style beats the stylesheet,
        // so setting display:flex made .tb-mobile-only { display:none } a no-op
        // and the bar showed on desktop too. globals.css owns visibility.
        borderTop: '0.5px solid var(--color-border-tertiary)',
        background: 'var(--color-background-secondary)',
        flexShrink: 0,
      }}
    >
      {TABS.map(({ href, label, Icon }) => {
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
      })}
    </nav>
  );
}
