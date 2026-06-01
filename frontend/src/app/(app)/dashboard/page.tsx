'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';

interface DashboardItem {
  topic_id: string;
  topic_name: string;
  frequency: string;
  last_scanned_at: string | null;
  new_count: number;
  update_count: number;
  preview_text: string;
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never scanned';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function DashboardPage() {
  const api = useApi();
  const router = useRouter();

  const { data: items = [], isLoading } = useQuery<DashboardItem[]>({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const r = await api.get('/dashboard');
      return r.data;
    },
    staleTime: 30_000,
  });

  return (
    <div style={{ flex: 1 }}>
      {/* Header */}
      <div style={{ padding: '20px 22px 16px' }}>
        <p style={{ fontSize: 20, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
          Dashboard
        </p>
      </div>

      {/* Cards */}
      <div style={{ padding: '0 22px 28px' }}>
        {isLoading && (
          <>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12, padding: '14px 16px', marginBottom: 10, background: 'var(--color-background-secondary)' }}>
                <div style={{ height: 13, width: '40%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 10 }} />
                <div style={{ height: 13, width: '90%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
                <div style={{ height: 13, width: '70%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
              </div>
            ))}
          </>
        )}

        {!isLoading && items.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 80, fontSize: 14, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
            You&apos;re all caught up.
          </div>
        )}

        {items.map(item => (
          <div
            key={item.topic_id}
            onClick={() => router.push(`/topics/${item.topic_id}`)}
            style={{
              border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12,
              padding: '14px 16px', marginBottom: 10, cursor: 'pointer',
              transition: 'border-color 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border-secondary)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border-tertiary)'; }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)' }}>{item.topic_name}</span>
              <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
                {timeAgo(item.last_scanned_at)} · {item.frequency ?? 'Auto'}
              </span>
            </div>

            {/* Badges */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
              {item.new_count > 0 && (
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: 'var(--tb-green-light)', color: 'var(--tb-green-dark)', fontWeight: 500 }}>
                  {item.new_count} new {item.new_count === 1 ? 'story' : 'stories'}
                </span>
              )}
              {item.update_count > 0 && (
                <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: 'var(--color-background-info)', color: 'var(--color-text-info)', fontWeight: 500 }}>
                  {item.update_count} {item.update_count === 1 ? 'update' : 'updates'}
                </span>
              )}
            </div>

            {/* Preview */}
            {item.preview_text && (
              <p style={{ fontSize: 13, color: 'var(--color-text-primary)', lineHeight: 1.5, marginBottom: 10, margin: '0 0 10px' }}>
                {item.preview_text}
              </p>
            )}

            {/* Link */}
            <span style={{ fontSize: 12, color: 'var(--color-text-info)', display: 'flex', alignItems: 'center', gap: 3 }}>
              Read brief <ArrowRight size={11} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
