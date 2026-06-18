'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import Link from 'next/link';
import { RefreshCw, AlertCircle } from 'lucide-react';

interface AdminMetrics {
  totals: {
    topics: number;
    briefs: number;
    facts: number;
    pipeline_runs: number;
    total_cost_usd: number;
    total_tokens: number;
    avg_duration_s: number;
  };
  runs_by_status: Record<string, number>;
  cost_by_stage: Record<string, number>;
  recent_runs: Array<{
    id: string;
    topic_id: string | null;
    started_at: string | null;
    duration_s: number | null;
    exit_status: string | null;
    brief_length: number;
    new: number;
    update: number;
    dupe: number;
    error: string | null;
  }>;
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-secondary)',
      borderRadius: 10,
      padding: '16px 20px',
    }}>
      <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--color-text-primary)', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function StatusBadge({ status }: { status: string | null }) {
  const s = (status ?? 'unknown').toLowerCase();
  const colors: Record<string, { bg: string; color: string }> = {
    success: { bg: 'var(--tb-green-light)', color: 'var(--tb-green-dark)' },
    failure: { bg: '#FEE2E2', color: '#991B1B' },
    revoked: { bg: '#FEF3C7', color: '#92400E' },
  };
  const c = colors[s] ?? { bg: 'var(--color-background-tertiary)', color: 'var(--color-text-secondary)' };
  return (
    <span style={{
      fontSize: 11, padding: '2px 7px', borderRadius: 6,
      background: c.bg, color: c.color, fontWeight: 500,
    }}>
      {status ?? 'unknown'}
    </span>
  );
}

export default function AdminPage() {
  const api = useApi();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<AdminMetrics>({
    queryKey: ['admin-metrics'],
    queryFn: async () => {
      const r = await api.get('/admin/metrics');
      return r.data;
    },
    staleTime: 30_000,
    retry: 0,
  });

  if (isLoading) {
    return (
      <div style={{ padding: 32, color: 'var(--color-text-secondary)', fontSize: 14 }}>
        Loading admin metrics…
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
          : `Failed to load metrics: ${(error as any)?.message ?? 'Unknown error'}`}
      </div>
    );
  }

  const t = data!.totals;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
            Admin Metrics
          </h1>
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '4px 0 0' }}>
            Pipeline health and LLM cost overview
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'var(--color-background-secondary)',
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 8, padding: '7px 14px',
            fontSize: 13, color: 'var(--color-text-primary)',
            cursor: 'pointer', fontFamily: 'inherit',
            opacity: isFetching ? 0.6 : 1,
          }}
        >
          <RefreshCw size={13} style={{ animation: isFetching ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* Stat grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
        <StatCard label="Topics" value={t.topics} />
        <StatCard label="Briefs" value={t.briefs} />
        <StatCard label="Facts" value={t.facts} />
        <StatCard label="Pipeline runs" value={t.pipeline_runs} />
        <StatCard label="Total cost" value={`$${t.total_cost_usd.toFixed(4)}`} sub="cumulative LLM spend" />
        <StatCard label="Total tokens" value={t.total_tokens.toLocaleString()} />
        <StatCard label="Avg duration" value={`${t.avg_duration_s}s`} sub="per pipeline run" />
        <StatCard
          label="Run status"
          value={Object.entries(data!.runs_by_status).map(([k, v]) => `${k}: ${v}`).join(' / ') || '—'}
        />
      </div>

      {/* Cost by stage */}
      {Object.keys(data!.cost_by_stage).length > 0 && (
        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
            LLM Cost by Stage
          </h2>
          <div style={{ background: 'var(--color-background-secondary)', border: '0.5px solid var(--color-border-secondary)', borderRadius: 10, overflow: 'hidden' }}>
            {Object.entries(data!.cost_by_stage).map(([stage, cost], i) => (
              <div key={stage} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 16px',
                borderTop: i > 0 ? '0.5px solid var(--color-border-tertiary)' : 'none',
              }}>
                <span style={{ fontSize: 13, color: 'var(--color-text-primary)', fontFamily: 'monospace' }}>{stage}</span>
                <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                  ${cost.toFixed(6)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Recent runs */}
      <section>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 4 }}>
          Recent Runs (last 25)
        </h2>
        <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '0 0 12px' }}>
          Click a run to open its full pipeline trace — query &amp; tools, articles, AI prompts/responses, and per-fact decisions.
        </p>
        <div style={{
          background: 'var(--color-background-secondary)',
          border: '0.5px solid var(--color-border-secondary)',
          borderRadius: 10, overflow: 'hidden',
        }}>
          {data!.recent_runs.length === 0 && (
            <div style={{ padding: '16px', fontSize: 13, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
              No runs yet.
            </div>
          )}
          {data!.recent_runs.map((run, i) => (
            <Link key={run.id} href={`/admin/runs/${run.id}`} style={{
              display: 'grid', gridTemplateColumns: '1fr 80px 70px 70px 70px 70px auto',
              alignItems: 'center', gap: 12,
              padding: '10px 16px', textDecoration: 'none',
              borderTop: i > 0 ? '0.5px solid var(--color-border-tertiary)' : 'none',
            }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--color-text-primary)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {run.topic_id ?? '—'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
                  {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
                </div>
              </div>
              <StatusBadge status={run.exit_status} />
              <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {run.duration_s != null ? `${run.duration_s}s` : '—'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--tb-green-dark)', textAlign: 'right' }} title="new facts">
                +{run.new}
              </span>
              <span style={{ fontSize: 12, color: 'var(--tb-amber)', textAlign: 'right' }} title="updated facts">
                ↑{run.update}
              </span>
              <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)', textAlign: 'right' }} title="duplicate facts">
                ={run.dupe}
              </span>
              <div style={{ fontSize: 11, color: '#DC2626', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {run.error ?? ''}
              </div>
            </Link>
          ))}
        </div>
      </section>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
