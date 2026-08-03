'use client';

/**
 * Topics index. Primarily a MOBILE screen — the desktop Sidebar already lists
 * topics, but the sidebar is hidden below 768px, so the "Topics" tab needs a
 * real destination rather than a slide-out menu.
 *
 * Renders on desktop too (harmless, and gives a wider overview than the rail).
 */

import { useRouter } from 'next/navigation';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { ChevronRight, Plus } from 'lucide-react';

interface Topic {
  id: string;
  raw_query: string;
  is_active: boolean;
  last_scan_at?: string | null;
  is_scanning?: boolean;
}

function relativeTime(iso?: string | null): string {
  if (!iso) return 'Never scanned';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'Never scanned';
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function SkeletonRow() {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '16px 16px',
        borderBottom: '0.5px solid var(--color-border-tertiary)',
      }}
    >
      <span className="tb-skeleton" style={{ width: 8, height: 8, borderRadius: '50%' }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 7 }}>
        <span className="tb-skeleton" style={{ height: 13, borderRadius: 5, width: '62%' }} />
        <span className="tb-skeleton" style={{ height: 10, borderRadius: 5, width: '30%' }} />
      </div>
    </div>
  );
}

export default function TopicsPage() {
  const router = useRouter();
  const api = useApi();

  const { data: topics, isLoading } = useQuery<Topic[]>({
    queryKey: ['topics'],
    queryFn: async () => {
      return (await api.get('/topics')).data;
    },
    staleTime: 10_000,
    refetchInterval: 8_000,
    // Default gcTime (5min) evicts the cache once this screen is unmounted
    // (switching tabs) for that long — coming back then re-shows the
    // skeleton as if it were a first-ever load. 30min covers realistic
    // between-tab-switches gaps without holding stale data forever.
    gcTime: 30 * 60_000,
    // Belt-and-suspenders on top of gcTime: whatever the exact trigger is
    // (cache eviction, a Supabase token-refresh re-render, a flaky mobile
    // network causing a background refetch to reset query status), never
    // drop back to a skeleton once real data has loaded once — keep
    // rendering the last known-good list instead.
    placeholderData: keepPreviousData,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <header
        style={{
          position: 'sticky', top: 0, zIndex: 10,
          background: 'var(--color-background-primary)',
          borderBottom: '0.5px solid var(--color-border-tertiary)',
          padding: '18px 16px 14px',
          display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12,
        }}
      >
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em', color: 'var(--color-text-primary)' }}>
          Topics
        </h1>
        {!!topics?.length && (
          <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
            {topics.length} tracked
          </span>
        )}
      </header>

      {isLoading && (
        <div>{[0, 1, 2, 3].map(i => <SkeletonRow key={i} />)}</div>
      )}

      {!isLoading && !topics?.length && (
        <div style={{ padding: '64px 28px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 500, color: 'var(--color-text-primary)' }}>
            No topics yet
          </p>
          <p style={{ margin: '0 0 20px', fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-tertiary)', maxWidth: 280 }}>
            Track a story once and TrueBrief only shows you what actually changed since last time.
          </p>
          <button
            onClick={() => router.push('/topics/new')}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 7,
              padding: '11px 18px', borderRadius: 10, border: 'none', cursor: 'pointer',
              background: 'var(--tb-green)', color: '#fff',
              fontSize: 14, fontWeight: 500, fontFamily: 'inherit',
            }}
          >
            <Plus size={16} />
            Track your first topic
          </button>
        </div>
      )}

      {topics?.map(topic => (
        <button
          key={topic.id}
          onClick={() => router.push(`/topics/${topic.id}`)}
          style={{
            display: 'flex', alignItems: 'center', gap: 12, width: '100%',
            padding: '15px 16px', border: 'none', background: 'none', cursor: 'pointer',
            borderBottom: '0.5px solid var(--color-border-tertiary)',
            textAlign: 'left', fontFamily: 'inherit',
            WebkitTapHighlightColor: 'transparent',
          }}
        >
          <span
            style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: topic.is_scanning ? 'var(--tb-amber)' : 'var(--color-border-secondary)',
              animation: topic.is_scanning ? 'tb-pulse 1.5s ease-in-out infinite' : undefined,
            }}
          />
          <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span
              style={{
                fontSize: 15, fontWeight: 500, color: 'var(--color-text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}
            >
              {topic.raw_query}
            </span>
            <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
              {topic.is_scanning ? 'Scanning…' : relativeTime(topic.last_scan_at)}
            </span>
          </span>
          <ChevronRight size={17} color="var(--color-text-tertiary)" style={{ flexShrink: 0 }} />
        </button>
      ))}
    </div>
  );
}
