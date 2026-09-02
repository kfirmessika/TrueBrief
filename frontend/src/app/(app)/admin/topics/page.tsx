'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { AlertCircle, Globe2, Lock } from 'lucide-react';

// Matches AdminTopicListItem in src/truebrief/api/routes.py (GET /admin/topics).
interface AdminTopic {
  id: string;
  name: string;
  raw_query: string;
  is_public: boolean;
  owner_id: string | null;
  owner_email: string | null;
  subscriber_count: number;
  is_active: boolean;
  last_run_at: string | null;
  created_at: string | null;
}

function VisibilityToggle({ topic, onToggle, pending }: {
  topic: AdminTopic;
  onToggle: () => void;
  pending: boolean;
}) {
  const c = topic.is_public
    ? { bg: 'var(--tb-green-light)', color: 'var(--tb-green-dark)' }
    : { bg: 'var(--color-background-tertiary)', color: 'var(--color-text-secondary)' };
  return (
    <button
      onClick={onToggle}
      disabled={pending}
      title={topic.is_public ? 'Make private' : 'Make public'}
      style={{
        display: 'flex', alignItems: 'center', gap: 5,
        fontSize: 11, padding: '3px 8px', borderRadius: 6,
        background: c.bg, color: c.color, fontWeight: 500,
        border: 'none', cursor: pending ? 'default' : 'pointer',
        fontFamily: 'inherit', opacity: pending ? 0.6 : 1,
      }}
    >
      {topic.is_public ? <Globe2 size={11} /> : <Lock size={11} />}
      {topic.is_public ? 'Public' : 'Private'}
    </button>
  );
}

function ActiveBadge({ isActive }: { isActive: boolean }) {
  const c = isActive
    ? { bg: 'var(--tb-green-light)', color: 'var(--tb-green-dark)' }
    : { bg: 'var(--color-background-tertiary)', color: 'var(--color-text-tertiary)' };
  return (
    <span style={{ fontSize: 11, padding: '2px 7px', borderRadius: 6, background: c.bg, color: c.color, fontWeight: 500 }}>
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

export default function AdminTopicsPage() {
  const api = useApi();
  const qc = useQueryClient();

  const { data, isLoading, isError, error } = useQuery<AdminTopic[]>({
    queryKey: ['admin-topics'],
    queryFn: async () => (await api.get('/admin/topics')).data,
    staleTime: 30_000,
    retry: 0,
  });

  const setVisibility = useMutation({
    mutationFn: async ({ id, isPublic }: { id: string; isPublic: boolean }) =>
      (await api.patch(`/admin/topics/${id}/public`, { is_public: isPublic })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-topics'] }),
  });

  if (isLoading) {
    return (
      <div style={{ padding: 32, color: 'var(--color-text-secondary)', fontSize: 14 }}>
        Loading topics…
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
          : `Failed to load topics: ${(error as any)?.message ?? 'Unknown error'}`}
      </div>
    );
  }

  const topics = data ?? [];

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          Topics
        </h1>
        <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '4px 0 0' }}>
          Every topic across every user ({topics.length}). Toggle visibility to publish/unpublish.
        </p>
      </div>

      <div style={{
        background: 'var(--color-background-secondary)',
        border: '0.5px solid var(--color-border-secondary)',
        borderRadius: 10, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '1.6fr 1fr 90px 80px 140px 80px',
          gap: 12, padding: '8px 16px',
          fontSize: 11, color: 'var(--color-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em',
          borderBottom: '0.5px solid var(--color-border-tertiary)',
        }}>
          <span>Query</span>
          <span>Owner</span>
          <span>Visibility</span>
          <span style={{ textAlign: 'right' }}>Subs</span>
          <span>Last run</span>
          <span>Status</span>
        </div>

        {topics.length === 0 && (
          <div style={{ padding: '16px', fontSize: 13, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
            No topics yet.
          </div>
        )}

        {topics.map((t) => (
          <div key={t.id} style={{
            display: 'grid', gridTemplateColumns: '1.6fr 1fr 90px 80px 140px 80px',
            alignItems: 'center', gap: 12,
            padding: '10px 16px',
            borderTop: '0.5px solid var(--color-border-tertiary)',
          }}>
            <span style={{
              fontSize: 13, color: 'var(--color-text-primary)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {t.raw_query}
            </span>
            <span style={{
              fontSize: 12, color: 'var(--color-text-secondary)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {t.owner_email ?? '—'}
            </span>
            <VisibilityToggle
              topic={t}
              pending={setVisibility.isPending && setVisibility.variables?.id === t.id}
              onToggle={() => setVisibility.mutate({ id: t.id, isPublic: !t.is_public })}
            />
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {t.subscriber_count}
            </span>
            <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
              {t.last_run_at ? new Date(t.last_run_at).toLocaleString() : '—'}
            </span>
            <ActiveBadge isActive={t.is_active} />
          </div>
        ))}
      </div>
    </div>
  );
}
