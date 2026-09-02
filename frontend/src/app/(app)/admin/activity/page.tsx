'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertCircle, ChevronDown, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import { useApi } from '@/lib/useApi';
import { STATUS_COLOR, STATUS_LABELS, type AdminRunRow } from '../_shared';

interface RunResponse { runs: AdminRunRow[]; next_offset: number | null; }

export default function AdminActivityPage() {
  const api = useApi();
  const [offset, setOffset] = useState(0);
  const [allRuns, setAllRuns] = useState<AdminRunRow[]>([]);
  const { data, isLoading, isError, refetch, isFetching } = useQuery<RunResponse>({
    queryKey: ['admin-runs', offset],
    queryFn: async () => (await api.get('/admin/runs', { params: { limit: 50, offset } })).data,
    staleTime: 15_000,
    retry: 0,
  });

  const currentRuns = offset === 0 ? (data?.runs ?? []) : [...allRuns, ...(data?.runs ?? [])];
  const loadMore = () => {
    if (!data?.next_offset) return;
    setAllRuns(currentRuns);
    setOffset(data.next_offset);
  };
  const refresh = () => { setAllRuns([]); setOffset(0); void refetch(); };

  if (isLoading && offset === 0) return <div style={{ padding: 32 }}>Loading activity…</div>;
  if (isError) return <div style={{ padding: 32, color: '#DC2626' }}><AlertCircle size={16} /> Could not load pipeline activity.</div>;

  return (
    <div style={{ maxWidth: 1180, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 8 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 21 }}>Pipeline activity</h1>
          <p style={{ margin: '5px 0 0', fontSize: 13, color: 'var(--color-text-tertiary)' }}>
            Every V5 scan. Open a row to see the grounded call, extraction, dedup, and brief trace.
          </p>
        </div>
        <button onClick={refresh} disabled={isFetching} style={buttonStyle}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div style={tableStyle}>
        <div style={headerStyle}>
          <span>Topic</span><span>Started</span><span>Status</span><span>Facts</span><span>Duration</span><span>Brief</span>
        </div>
        {currentRuns.map(run => (
          <Link href={`/admin/runs/${run.id}`} key={run.id} style={{ ...headerStyle, textDecoration: 'none', color: 'inherit', borderTop: '0.5px solid var(--color-border-tertiary)' }}>
            <span style={topicStyle}>{run.topic_name || 'Unknown topic'}</span>
            <span>{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</span>
            <span style={{ color: STATUS_COLOR[run.exit_status ?? ''] ?? 'var(--color-text-secondary)', fontWeight: 600 }}>
              {STATUS_LABELS[run.exit_status ?? ''] ?? run.exit_status ?? 'unknown'}
            </span>
            <span>{run.new} new · {run.update} update · {run.dupe} dupes</span>
            <span>{run.duration_s == null ? '—' : `${run.duration_s}s`}</span>
            <span>{run.brief_length ? `${run.brief_length.toLocaleString()} chars` : 'No brief'}</span>
          </Link>
        ))}
        {currentRuns.length === 0 && <p style={{ padding: 18, color: 'var(--color-text-tertiary)' }}>No pipeline runs yet.</p>}
      </div>

      {data?.next_offset != null && (
        <button onClick={loadMore} disabled={isFetching} style={{ ...buttonStyle, margin: '16px auto', display: 'flex' }}>
          <ChevronDown size={14} /> Load 50 more runs
        </button>
      )}
    </div>
  );
}

const tableStyle: React.CSSProperties = { background: 'var(--color-background-secondary)', border: '0.5px solid var(--color-border-secondary)', borderRadius: 10, overflow: 'hidden', marginTop: 24 };
const headerStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1.5fr 170px 110px 180px 85px 110px', gap: 12, alignItems: 'center', padding: '11px 16px', fontSize: 12 };
const topicStyle: React.CSSProperties = { fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' };
const buttonStyle: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: 6, border: '0.5px solid var(--color-border-secondary)', borderRadius: 8, background: 'var(--color-background-secondary)', color: 'var(--color-text-primary)', padding: '8px 12px', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' };
