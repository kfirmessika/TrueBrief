'use client';

import { use } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import Link from 'next/link';
import { AlertCircle, ArrowLeft, Globe2, Lock } from 'lucide-react';
import { StatCard, RunRowList, type AdminRunRow } from '../../_shared';

// Matches GET /admin/users/{user_id} in src/truebrief/api/routes.py. Note the
// response nests profile fields under `user`, and the subscribed-topics list
// is `watch_list` (not `subscribed_topics`) — verified against the live route,
// not guessed.
interface AdminTopicSummary {
  id: string;
  name: string;
  raw_query: string;
  is_public: boolean;
  last_run_at: string | null;
}

interface AdminUserDetail {
  user: {
    id: string;
    email: string;
    tier: string;
    created_at: string | null;
  };
  created_topics: AdminTopicSummary[];
  watch_list: AdminTopicSummary[];
  recent_runs: AdminRunRow[];
  usage: {
    total_cost_usd: number;
    total_tokens: number;
    run_count: number;
  };
}

function TopicVisibilityBadge({ isPublic }: { isPublic: boolean }) {
  const c = isPublic
    ? { bg: 'var(--tb-green-light)', color: 'var(--tb-green-dark)' }
    : { bg: 'var(--color-background-tertiary)', color: 'var(--color-text-secondary)' };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '2px 7px', borderRadius: 6, background: c.bg, color: c.color, fontWeight: 500 }}>
      {isPublic ? <Globe2 size={11} /> : <Lock size={11} />}
      {isPublic ? 'Public' : 'Private'}
    </span>
  );
}

function TopicList({ topics, emptyLabel }: { topics: AdminTopicSummary[]; emptyLabel: string }) {
  return (
    <div style={{
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-secondary)',
      borderRadius: 10, overflow: 'hidden',
    }}>
      {topics.length === 0 && (
        <div style={{ padding: '16px', fontSize: 13, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
          {emptyLabel}
        </div>
      )}
      {topics.map((t, i) => (
        <div key={t.id} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
          padding: '10px 16px',
          borderTop: i > 0 ? '0.5px solid var(--color-border-tertiary)' : 'none',
        }}>
          <span style={{
            fontSize: 13, color: 'var(--color-text-primary)', flex: 1,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {t.name}
          </span>
          <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', flexShrink: 0 }}>
            {t.last_run_at ? new Date(t.last_run_at).toLocaleString() : 'never run'}
          </span>
          <TopicVisibilityBadge isPublic={t.is_public} />
        </div>
      ))}
    </div>
  );
}

export default function AdminUserDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const api = useApi();

  const { data, isLoading, isError, error } = useQuery<AdminUserDetail>({
    queryKey: ['admin-user', id],
    queryFn: async () => (await api.get(`/admin/users/${id}`)).data,
    staleTime: 30_000,
    retry: 0,
  });

  if (isLoading) {
    return (
      <div style={{ padding: 32, color: 'var(--color-text-secondary)', fontSize: 14 }}>
        Loading user…
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
          : status === 404
            ? 'User not found.'
            : `Failed to load user: ${(error as any)?.message ?? 'Unknown error'}`}
      </div>
    );
  }

  const { user, created_topics, watch_list, recent_runs, usage } = data!;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px' }}>
      <Link href="/admin/users" style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        fontSize: 12, color: 'var(--color-text-tertiary)', textDecoration: 'none', marginBottom: 16,
      }}>
        <ArrowLeft size={13} /> Back to Users
      </Link>

      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {user.email}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '4px 0 0' }}>
          {user.tier} tier · joined {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
        </p>
      </div>

      {/* Usage */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 28 }}>
        <StatCard label="Total cost" value={`$${usage.total_cost_usd.toFixed(4)}`} sub="across this user's created topics" />
        <StatCard label="Total tokens" value={usage.total_tokens.toLocaleString()} />
        <StatCard label="Pipeline runs" value={usage.run_count} />
      </div>

      {/* Created topics */}
      <section style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
          Created Topics <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12 }}>({created_topics.length})</span>
        </h2>
        <TopicList topics={created_topics} emptyLabel="Hasn't created any topics." />
      </section>

      {/* Subscribed topics */}
      <section style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
          Subscribed Topics <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12 }}>({watch_list.length})</span>
        </h2>
        <TopicList topics={watch_list} emptyLabel="Not subscribed to any topics." />
      </section>

      {/* Recent runs */}
      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 4 }}>
          Recent Runs <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12 }}>(last 25, this user's topics only)</span>
        </h2>
        <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '0 0 12px' }}>
          Click a run to open its full pipeline trace.
        </p>
        <RunRowList runs={recent_runs} />
      </section>
    </div>
  );
}
