'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import Link from 'next/link';
import { RefreshCw, AlertCircle, GitCompare } from 'lucide-react';

interface QuotaAlert {
  id: string;
  created_at: string;
  severity: 'yellow' | 'red';
  step_name: string;
  model: string;
  key_type: 'primary' | 'backup';
  error_detail: string | null;
  notified: boolean;
}

interface QuotaAlertsResponse {
  alerts: QuotaAlert[];
  red_count: number;
  yellow_count: number;
}

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
  benchmark_cost_usd: number;
  benchmark_cost_by_stage: Record<string, number>;
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

// Raw pipeline_run.exit_status / llm_call_log.stage values, for a founder-facing label
// instead of the internal snake_case name. Anything not listed here still renders —
// this is cosmetic, not a whitelist.
const STAGE_LABELS: Record<string, string> = {
  gemini_search: 'Search (Gemini)',
  gemini_extract: 'Extraction',
  arbiter: 'Dedup / Judge',
  briefer: 'Brief writing',
  embedding: 'Embedding (memory)',
  signal_scorer: 'Signal scoring',
  query_builder: 'Query building',
  harvester: 'Harvesting (V4)',
  story_stitch: 'Story stitching',
  story_summarizer: 'Story summary',
};
const STATUS_LABELS: Record<string, string> = {
  success: 'Success', running: 'Running', error: 'Error',
  no_update: 'No new facts', failure: 'Failure',
};
const STATUS_COLOR: Record<string, string> = {
  success: 'var(--tb-green-dark)', running: 'var(--tb-amber)',
  error: '#DC2626', failure: '#DC2626', no_update: 'var(--color-text-tertiary)',
};

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

// Founder-facing labels for llm_call_log stage names / model ids, reused from the
// STAGE_LABELS map below where the key matches; falls back to the raw string.
function stepLabel(step: string): string {
  return STAGE_LABELS[step] ?? step;
}

function QuotaAlertsBanner() {
  const api = useApi();

  const { data, isLoading, isError } = useQuery<QuotaAlertsResponse>({
    queryKey: ['admin-quota-alerts'],
    queryFn: async () => {
      const r = await api.get('/admin/quota-alerts', { params: { hours: 48 } });
      return r.data;
    },
    staleTime: 30_000,
    retry: 0,
    // Quota exhaustion is time-sensitive — poll so this banner stays live without a
    // manual refresh, same rhythm as the scan-status poll elsewhere in the app.
    refetchInterval: 60_000,
  });

  if (isLoading || isError || !data || data.alerts.length === 0) {
    return null;
  }

  const reds = data.alerts.filter((a) => a.severity === 'red');
  const yellows = data.alerts.filter((a) => a.severity === 'yellow');

  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
        Gemini Quota Alerts <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12 }}>(last 48h)</span>
      </h2>

      {reds.length > 0 && (
        <div style={{
          background: '#FEF2F2',
          border: '1px solid #FCA5A5',
          borderRadius: 10,
          padding: '14px 16px',
          marginBottom: yellows.length > 0 ? 10 : 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <AlertCircle size={16} color="#DC2626" />
            <span style={{ fontSize: 13, fontWeight: 700, color: '#991B1B' }}>
              {reds.length} critical — calls failing/degraded
            </span>
          </div>
          {reds.slice(0, 10).map((a) => (
            <div key={a.id} style={{
              fontSize: 12, color: '#7F1D1D', padding: '4px 0',
              borderTop: '1px solid #FCA5A5',
            }}>
              <span style={{ fontFamily: 'monospace' }}>{new Date(a.created_at).toLocaleString()}</span>
              {' — '}
              <strong>{stepLabel(a.step_name)}</strong> / {a.model} ({a.key_type} key)
              {a.notified ? '' : ' — push not delivered'}
            </div>
          ))}
        </div>
      )}

      {yellows.length > 0 && (
        <div style={{
          background: '#FFFBEB',
          border: '1px solid #FDE68A',
          borderRadius: 10,
          padding: '14px 16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <AlertCircle size={16} color="#B45309" />
            <span style={{ fontSize: 13, fontWeight: 600, color: '#92400E' }}>
              {yellows.length} warning — primary key exhausted, running on backup
            </span>
          </div>
          {yellows.slice(0, 10).map((a) => (
            <div key={a.id} style={{
              fontSize: 12, color: '#78350F', padding: '4px 0',
              borderTop: '1px solid #FDE68A',
            }}>
              <span style={{ fontFamily: 'monospace' }}>{new Date(a.created_at).toLocaleString()}</span>
              {' — '}
              {stepLabel(a.step_name)} / {a.model}
            </div>
          ))}
        </div>
      )}
    </section>
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Link
            href="/admin/compare"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--color-background-secondary)',
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 8, padding: '7px 14px',
              fontSize: 13, color: 'var(--color-text-primary)',
              cursor: 'pointer', textDecoration: 'none',
            }}
          >
            <GitCompare size={13} />
            Compare briefs
          </Link>
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
      </div>

      <QuotaAlertsBanner />

      {/* Stat grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
        <StatCard label="Topics" value={t.topics} />
        <StatCard label="Briefs" value={t.briefs} />
        <StatCard label="Facts" value={t.facts} />
        <StatCard label="Pipeline runs" value={t.pipeline_runs} />
        <StatCard label="Total cost" value={`$${t.total_cost_usd.toFixed(4)}`} sub="V5 production spend" />
        <StatCard label="Total tokens" value={t.total_tokens.toLocaleString()} />
        <StatCard label="Avg duration" value={`${t.avg_duration_s}s`} sub="per pipeline run" />
      </div>

      {/* Run status — was one crammed "k: v / k: v" string in a stat tile; a real
          breakdown reads in a glance instead of requiring the tile be parsed. */}
      {Object.keys(data!.runs_by_status).length > 0 && (
        <section style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
            Run Status <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12 }}>(last {t.pipeline_runs})</span>
          </h2>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {Object.entries(data!.runs_by_status)
              .sort((a, b) => b[1] - a[1])
              .map(([status, count]) => (
                <div key={status} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 20, fontWeight: 600, color: STATUS_COLOR[status] ?? 'var(--color-text-primary)' }}>
                    {count}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>
                    {STATUS_LABELS[status] ?? status}
                  </span>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Cost by stage — non-zero stages only; a $0.000000 row next to real spend reads
          as broken tracking, not "this stage happens to be free". The 4 live V5 stages
          (search, extraction, dedup/judge, brief writing) all make priced LLM calls, but
          arbiter legitimately shows $0 in a window with no grey-zone facts to judge. */}
      {(() => {
        const priced = Object.entries(data!.cost_by_stage)
          .filter(([, cost]) => cost > 0)
          .sort((a, b) => b[1] - a[1]);
        const freeCount = Object.keys(data!.cost_by_stage).length - priced.length;
        if (priced.length === 0) return null;
        return (
          <section style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 12 }}>
              LLM Cost by Stage
            </h2>
            <div style={{ background: 'var(--color-background-secondary)', border: '0.5px solid var(--color-border-secondary)', borderRadius: 10, overflow: 'hidden' }}>
              {priced.map(([stage, cost], i) => (
                <div key={stage} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderTop: i > 0 ? '0.5px solid var(--color-border-tertiary)' : 'none',
                }}>
                  <span style={{ fontSize: 13, color: 'var(--color-text-primary)' }}>{STAGE_LABELS[stage] ?? stage}</span>
                  <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                    ${cost.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
            {freeCount > 0 && (
              <p style={{ fontSize: 11, color: 'var(--color-text-tertiary)', margin: '6px 0 0' }}>
                +{freeCount} other stage{freeCount === 1 ? '' : 's'} had no calls in this window
              </p>
            )}
          </section>
        );
      })()}

      {/* Benchmark spend — scripts/quality_benchmark.py runs V4's PipelineRunner (harvester,
          query_builder, signal_scorer, ...) on throwaway topics for the A/B comparison, and
          logs to the same llm_call_log table as production. Kept separate and collapsed by
          default so it never reads as V5 production cost. */}
      {data!.benchmark_cost_usd > 0 && (
        <details style={{ marginBottom: 28 }}>
          <summary style={{
            fontSize: 13, color: 'var(--color-text-tertiary)', cursor: 'pointer',
            userSelect: 'none',
          }}>
            Benchmark spend (V4, not production): ${data!.benchmark_cost_usd.toFixed(4)}
          </summary>
          <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '8px 0' }}>
            From scripts/quality_benchmark.py's V4-vs-V5 comparison runs on throwaway topics —
            not part of the live V5 pipeline.
          </p>
          <div style={{ background: 'var(--color-background-secondary)', border: '0.5px solid var(--color-border-secondary)', borderRadius: 10, overflow: 'hidden' }}>
            {Object.entries(data!.benchmark_cost_by_stage)
              .sort((a, b) => b[1] - a[1])
              .map(([stage, cost], i) => (
                <div key={stage} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderTop: i > 0 ? '0.5px solid var(--color-border-tertiary)' : 'none',
                }}>
                  <span style={{ fontSize: 13, color: 'var(--color-text-primary)' }}>{STAGE_LABELS[stage] ?? stage}</span>
                  <span style={{ fontSize: 13, color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                    ${cost.toFixed(4)}
                  </span>
                </div>
              ))}
          </div>
        </details>
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
