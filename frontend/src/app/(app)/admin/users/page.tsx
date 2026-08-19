'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import Link from 'next/link';
import { AlertCircle } from 'lucide-react';

// Matches AdminUserListItem in src/truebrief/api/routes.py (GET /admin/users).
interface AdminUser {
  id: string;
  email: string;
  tier: string;
  created_at: string | null;
  topics_created: number;
  subscriptions: number;
}

const TIER_COLOR: Record<string, { bg: string; color: string }> = {
  free: { bg: 'var(--color-background-tertiary)', color: 'var(--color-text-tertiary)' },
  pro: { bg: 'var(--tb-green-light)', color: 'var(--tb-green-dark)' },
};

function TierBadge({ tier }: { tier: string }) {
  const c = TIER_COLOR[tier] ?? { bg: 'var(--color-background-tertiary)', color: 'var(--color-text-secondary)' };
  return (
    <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 6, background: c.bg, color: c.color, fontWeight: 500, textTransform: 'capitalize' }}>
      {tier}
    </span>
  );
}

export default function AdminUsersPage() {
  const api = useApi();

  const { data, isLoading, isError, error } = useQuery<AdminUser[]>({
    queryKey: ['admin-users'],
    queryFn: async () => (await api.get('/admin/users')).data,
    staleTime: 30_000,
    retry: 0,
  });

  if (isLoading) {
    return (
      <div style={{ padding: 32, color: 'var(--color-text-secondary)', fontSize: 14 }}>
        Loading users…
      </div>
    );
  }

  if (isError) {
    const status = (error as any)?.response?.status;
    return (
      <div style={{ padding: 32, display: 'flex', alignItems: 'center', gap: 10, color: '#DC2626', fontSize: 14 }}>
        <AlertCircle size={18} />
        {status === 403
          ? 'Access denied. Your account is not in ADMIN_USER_IDS.'
          : `Failed to load users: ${(error as any)?.message ?? 'Unknown error'}`}
      </div>
    );
  }

  const users = data ?? [];

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Users
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '4px 0 0' }}>
          {users.length} registered user{users.length === 1 ? '' : 's'}. Click a row for usage and pipeline history.
        </p>
      </div>

      <div style={{
        background: 'var(--color-background-secondary)',
        border: '0.5px solid var(--color-border-secondary)',
        borderRadius: 10, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '1.6fr 80px 100px 110px 160px',
          gap: 12, padding: '8px 16px',
          fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em',
          borderBottom: '0.5px solid var(--color-border-tertiary)',
        }}>
          <span>Email</span>
          <span>Tier</span>
          <span style={{ textAlign: 'right' }}>Topics</span>
          <span style={{ textAlign: 'right' }}>Subs</span>
          <span>Joined</span>
        </div>

        {users.length === 0 && (
          <div style={{ padding: '16px', fontSize: 13, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
            No users yet.
          </div>
        )}

        {users.map((u) => (
          <Link key={u.id} href={`/admin/users/${u.id}`} style={{
            display: 'grid', gridTemplateColumns: '1.6fr 80px 100px 110px 160px',
            alignItems: 'center', gap: 12,
            padding: '10px 16px', textDecoration: 'none',
            borderTop: '0.5px solid var(--color-border-tertiary)',
          }}>
            <span style={{
              fontSize: 13, color: 'var(--color-text-primary)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {u.email}
            </span>
            <TierBadge tier={u.tier} />
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {u.topics_created}
            </span>
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {u.subscriptions}
            </span>
            <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
              {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
