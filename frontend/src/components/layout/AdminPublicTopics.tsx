'use client';

/**
 * Admin-only sidebar section. Visually separated from "My topics" (own <hr> +
 * header, rendered as its own block) per the spec — never interleaved with the
 * user's private topic list. Inline CSS-var styles to match the Sidebar
 * convention (see frontend CLAUDE.md "Styling split") — this is shell chrome,
 * not a Tailwind component.
 *
 * Admin-ness is NOT re-checked here — the caller (Sidebar) only renders this
 * when /users/me/stats.is_admin is true, and every mutation below hits a
 * server route that independently enforces _require_admin regardless.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { EyeOff, Plus, Globe2 } from 'lucide-react';

interface PublicTopic { id: string; name: string; subscriber_count: number }

export default function AdminPublicTopics() {
  const api = useApi();
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newQuery, setNewQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { data: topics = [] } = useQuery<PublicTopic[]>({
    queryKey: ['public-topics'],
    queryFn: async () => (await api.get('/public-topics')).data,
    staleTime: 30_000,
  });

  const createPublic = useMutation({
    mutationFn: async (raw_query: string) => (await api.post('/admin/public-topics', { raw_query })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['public-topics'] });
      // Backend auto-subscribes the admin to the topic it just created/promoted.
      qc.invalidateQueries({ queryKey: ['topics'] });
      setNewQuery('');
      setShowAdd(false);
      setError(null);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Failed to create public topic.');
    },
  });

  const setVisibility = useMutation({
    mutationFn: async ({ id, isPublic }: { id: string; isPublic: boolean }) =>
      (await api.patch(`/admin/topics/${id}/public`, { is_public: isPublic })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['public-topics'] }),
  });

  return (
    <>
      <hr style={{ border: 'none', borderTop: '0.5px solid var(--color-border-tertiary)', margin: '4px 10px' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px 3px' }}>
        <span style={{
          fontSize: 10, color: 'var(--color-text-tertiary)', letterSpacing: '0.06em',
          textTransform: 'uppercase', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <Globe2 size={11} /> Public topics
        </span>
        <button
          onClick={() => setShowAdd(v => !v)}
          title="Add a public topic"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-tertiary)', display: 'flex', padding: 2 }}
        >
          <Plus size={13} />
        </button>
      </div>

      {showAdd && (
        <div style={{ padding: '2px 12px 8px' }}>
          <input
            value={newQuery}
            onChange={e => setNewQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && newQuery.trim() && !createPublic.isPending) createPublic.mutate(newQuery.trim()); }}
            placeholder="New public topic…"
            style={{
              width: '100%', fontSize: 12, padding: '6px 8px', borderRadius: 6,
              border: '0.5px solid var(--color-border-secondary)',
              background: 'var(--color-background-primary)', color: 'var(--color-text-primary)',
              fontFamily: 'inherit', boxSizing: 'border-box',
            }}
          />
          {error && <p style={{ fontSize: 10.5, color: '#B91C1C', margin: '4px 0 0' }}>{error}</p>}
        </div>
      )}

      {topics.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', padding: '2px 14px 8px', fontStyle: 'italic' }}>
          No public topics yet
        </div>
      )}

      {topics.map(t => (
        <div key={t.id} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 12px', margin: '1px 8px', borderRadius: 8,
        }}>
          <span style={{
            fontSize: 13, color: 'var(--color-text-primary)', flex: 1,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {t.name}
          </span>
          <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', flexShrink: 0 }}>
            {t.subscriber_count}
          </span>
          <button
            onClick={() => setVisibility.mutate({ id: t.id, isPublic: false })}
            title="Make private"
            disabled={setVisibility.isPending}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-tertiary)', display: 'flex', padding: 2, flexShrink: 0 }}
          >
            <EyeOff size={13} />
          </button>
        </div>
      ))}
    </>
  );
}
