'use client';

/**
 * Tab bar shared across every /admin/* screen.
 * Each tab is a real route (its own page.tsx) — this layout only renders the
 * nav chrome and {children} below it. Admin-ness is enforced per-page (each
 * page's own query 403s and shows "Access denied" if the caller isn't an
 * admin), same as admin/page.tsx already did — no gating logic added here.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS: Array<{ href: string; label: string }> = [
  { href: '/admin', label: 'Overview' },
  { href: '/admin/activity', label: 'Activity' },
  { href: '/admin/services', label: 'Services' },
  { href: '/admin/costs', label: 'Costs' },
  { href: '/admin/topics', label: 'Topics' },
  { href: '/admin/users', label: 'Users' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div>
      <div style={{ borderBottom: '0.5px solid var(--color-border-secondary)' }}>
        <nav style={{
          display: 'flex', gap: 4, maxWidth: 1000, margin: '0 auto', padding: '0 24px',
        }}>
          {TABS.map((tab) => {
            // Overview is "/admin" exactly — startsWith would also match every
            // other tab's path. Everything else (including /admin/users/{id})
            // uses startsWith so the drill-down keeps "Users" highlighted.
            const active = tab.href === '/admin'
              ? pathname === '/admin'
              : pathname === tab.href || pathname.startsWith(`${tab.href}/`);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                style={{
                  padding: '12px 14px',
                  fontSize: 13,
                  fontWeight: 500,
                  color: active ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                  textDecoration: 'none',
                  borderBottom: active ? '2px solid var(--tb-green)' : '2px solid transparent',
                  marginBottom: -0.5,
                }}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>
      {children}
    </div>
  );
}
