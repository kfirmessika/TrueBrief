'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import Link from 'next/link';
import { RefreshCw, AlertCircle, DollarSign, Pause, Play } from 'lucide-react';
import { StatCard, STAGE_LABELS, STATUS_COLOR, STATUS_LABELS, stepLabel, RunRowList } from './_shared';

interface QuotaAlert {
  id: string;
  created_at: string;
  severity: 'yellow' | 'red';
  step_name: string;
  model: string;
  key_type: 'primary' | 'backup' | 'rpm' | 'single';
  error_detail: string | null;
  notified: boolean;
  provider?: string;
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
        Provider Alerts <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12 }}>(last 48h)</span>
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
              {reds.length} critical — no working fallback left, calls failing/degraded
            </span>
          </div>
          {reds.slice(0, 10).map((a) => (
            <div key={a.id} style={{
              fontSize: 12, color: '#7F1D1D', padding: '4px 0',
              borderTop: '1px solid #FCA5A5',
            }}>
              <span style={{ fontFamily: 'monospace' }}>{new Date(a.created_at).toLocaleString()}</span>
              {' — '}
              <strong>{(a.provider ?? 'gemini').toUpperCase()}</strong> · {stepLabel(a.step_name)} / {a.model}
              {a.key_type === 'primary' || a.key_type === 'backup' ? ` (${a.key_type} key)` : ''}
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
              {yellows.length} warning — a provider failed, fallback covered it
            </span>
          </div>
          {yellows.slice(0, 10).map((a) => (
            <div key={a.id} style={{
              fontSize: 12, color: '#78350F', padding: '4px 0',
              borderTop: '1px solid #FDE68A',
            }}>
              <span style={{ fontFamily: 'monospace' }}>{new Date(a.created_at).toLocaleString()}</span>
              {' — '}
              <strong>{(a.provider ?? 'gemini').toUpperCase()}</strong> · {stepLabel(a.step_name)} / {a.model}
              {a.key_type === 'primary' || a.key_type === 'backup' ? ` (${a.key_type} key)` : ''}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

interface KeyStatus {
  state: 'ok' | 'rpm_limited' | 'rpd_exhausted' | 'unknown';
  last_event_at: string | null;
  last_event_type: 'rpm' | 'rpd' | null;
  configured?: boolean;
}

interface KeyStatusResponse {
  primary_key: KeyStatus;
  backup_key: KeyStatus & { configured: boolean };
  model_usage_today: Record<string, number>;
  rpd_limits: Record<string, number>;
  embed_provider: string;
  search_provider: string;
}

function KeyStatusPanel() {
  const api = useApi();
  const { data, isLoading } = useQuery<KeyStatusResponse>({
    queryKey: ['admin-key-status'],
    queryFn: async () => (await api.get('/admin/key-status')).data,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 0,
  });

  if (isLoading || !data) return null;

  const stateColor = (s: KeyStatus['state']) =>
    s === 'ok' ? '#16A34A' : s === 'rpm_limited' ? '#B45309' : s === 'rpd_exhausted' ? '#DC2626' : '#6B7280';
  const stateLabel = (s: KeyStatus['state']) =>
    s === 'ok' ? 'No recent quota error' : s === 'rpm_limited' ? 'RPM limit (retrying)' : s === 'rpd_exhausted' ? 'RPD exhausted' : 'Unknown';
  const stateDesc = (s: KeyStatus) =>
    s.state === 'rpm_limited'
      ? 'Per-minute rate limit hit — auto-retries after 65s, no action needed'
      : s.state === 'rpd_exhausted'
      ? `Daily quota exhausted${s.last_event_at ? ' since ' + new Date(s.last_event_at).toLocaleTimeString() : ''} — reset time is provider-specific; verify it in the provider console`
      : null;

  const MODEL_LABELS: Record<string, string> = {
    'gemini-3.5-flash-lite': '3.5 Flash Lite',
    'gemini-3.1-flash-lite': '3.1 Flash Lite',
    'gemini-2.5-flash-lite': '2.5 Flash Lite',
    'models/gemini-embedding-2': 'Embedding 2',
  };

  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 4 }}>
        Gemini quota signals
        <span style={{ fontWeight: 400, color: 'var(--color-text-tertiary)', fontSize: 12, marginLeft: 8 }}>recorded by TrueBrief · refreshes every 60s</span>
      </h2>
      <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginBottom: 12 }}>
        Configured now — search: <strong style={{ color: 'var(--color-text-secondary)' }}>{data.search_provider}</strong>, embed: <strong style={{ color: 'var(--color-text-secondary)' }}>{data.embed_provider}</strong>.
        {data.search_provider !== 'gemini' && ' Gemini can still show up below as an automatic grounding fallback.'}
      </div>

      {/* Key status cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        {([['Primary key', data.primary_key], ['Backup key', data.backup_key]] as const).map(([label, key]) => (
          <div key={label} style={{
            background: 'var(--color-background-secondary)',
            border: `1px solid ${key.state !== 'ok' ? stateColor(key.state) + '66' : 'var(--color-border-secondary)'}`,
            borderRadius: 10, padding: '14px 16px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%',
                background: stateColor(key.state), flexShrink: 0,
                boxShadow: key.state !== 'ok' ? `0 0 6px ${stateColor(key.state)}` : 'none',
              }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>{label}</span>
              {'configured' in key && !key.configured && (
                <span style={{ fontSize: 11, color: '#DC2626', marginLeft: 4 }}>not configured</span>
              )}
              <span style={{ fontSize: 12, color: stateColor(key.state), marginLeft: 'auto', fontWeight: 600 }}>
                {stateLabel(key.state)}
              </span>
            </div>
            {stateDesc(key) && (
              <p style={{ fontSize: 11, color: 'var(--color-text-tertiary)', margin: 0, paddingLeft: 16 }}>
                {stateDesc(key)}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Today's model usage vs RPD limits */}
      {Object.keys(data.model_usage_today).length > 0 && (
        <div style={{ background: 'var(--color-background-secondary)', border: '1px solid var(--color-border-secondary)', borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 10 }}>
            Recorded calls today (UTC)
          </div>
          {Object.entries(data.model_usage_today)
            .filter(([m]) => !m.startsWith('local/'))
            .sort((a, b) => b[1] - a[1])
            .map(([model, calls]) => {
              const limit = data.rpd_limits[model];
              const pct = limit ? Math.round((calls / limit) * 100) : null;
              const barColor = pct == null ? '#94A3B8' : pct >= 90 ? '#DC2626' : pct >= 70 ? '#B45309' : '#16A34A';
              return (
                <div key={model} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', width: 120, flexShrink: 0 }}>
                    {MODEL_LABELS[model] ?? model}
                  </span>
                  <div style={{ flex: 1, background: 'var(--color-border-secondary)', borderRadius: 4, height: 6 }}>
                    {pct != null && (
                      <div style={{ width: `${Math.min(pct, 100)}%`, background: barColor, borderRadius: 4, height: 6, transition: 'width 0.3s' }} />
                    )}
                  </div>
                  <span style={{ fontSize: 12, color: pct != null && pct >= 70 ? barColor : 'var(--color-text-tertiary)', width: 80, textAlign: 'right' }}>
                    {calls}{limit ? ` / ${limit}` : ''}{pct != null ? ` (${pct}%)` : ''}
                  </span>
                </div>
              );
            })}
          <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginTop: 6 }}>
            Embed: <strong>{data.embed_provider === 'local' ? 'local (no quota)' : 'Gemini API'}</strong>
            {data.embed_provider === 'gemini' && ' — set EMBED_PROVIDER=local to remove quota dependency'}
          </div>
        </div>
      )}
    </section>
  );
}

function FreezeToggle() {
  const api = useApi();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<{ frozen: boolean }>({
    queryKey: ['admin-automation-freeze'],
    queryFn: async () => (await api.get('/admin/automation-freeze')).data,
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: 0,
  });

  const mutation = useMutation({
    mutationFn: async (frozen: boolean) => {
      await api.post('/admin/automation-freeze', { frozen });
      return frozen;
    },
    onSuccess: (frozen) => {
      qc.setQueryData(['admin-automation-freeze'], { frozen });
    },
  });

  const frozen = data?.frozen ?? false;
  const pending = mutation.isPending;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      background: frozen
        ? 'linear-gradient(135deg, #1a0a0a 0%, #2d0f0f 100%)'
        : 'var(--color-background-secondary)',
      border: `1.5px solid ${frozen ? '#DC2626' : 'var(--color-border-secondary)'}`,
      borderRadius: 12,
      padding: '14px 18px',
      marginBottom: 24,
      transition: 'all 0.25s ease',
    }}>
      {/* Status indicator */}
      <div style={{
        width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
        background: frozen ? '#DC2626' : '#16A34A',
        boxShadow: frozen ? '0 0 8px #DC2626' : '0 0 6px #16A34A',
        animation: frozen ? 'pulse-red 1.8s ease-in-out infinite' : 'none',
      }} />

      {/* Label */}
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: 13, fontWeight: 700,
          color: frozen ? '#FCA5A5' : 'var(--color-text-primary)',
        }}>
          {frozen ? 'Automation FROZEN' : 'Automation running'}
        </div>
        <div style={{ fontSize: 11, color: frozen ? '#F87171' : 'var(--color-text-tertiary)', marginTop: 2 }}>
          {frozen
            ? 'Scheduler is paused — no topics will auto-run. Manual runs still work.'
            : 'Scheduler is active — topics run on their configured schedule.'}
        </div>
      </div>

      {/* Toggle button */}
      <button
        onClick={() => mutation.mutate(!frozen)}
        disabled={isLoading || pending}
        style={{
          display: 'flex', alignItems: 'center', gap: 7,
          background: frozen ? '#DC2626' : 'var(--color-background-tertiary, #F3F4F6)',
          border: `1px solid ${frozen ? '#B91C1C' : 'var(--color-border-secondary)'}`,
          borderRadius: 8, padding: '8px 16px',
          fontSize: 13, fontWeight: 600,
          color: frozen ? '#fff' : 'var(--color-text-primary)',
          cursor: isLoading || pending ? 'not-allowed' : 'pointer',
          fontFamily: 'inherit',
          opacity: isLoading || pending ? 0.6 : 1,
          transition: 'all 0.2s ease',
          whiteSpace: 'nowrap',
        }}
      >
        {frozen
          ? <><Play size={13} /> Unfreeze</>
          : <><Pause size={13} /> Freeze automation</>}
      </button>

      <style>{`
        @keyframes pulse-red {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(0.85); }
        }
      `}</style>
    </div>
  );
}

function CostSnapshot() {
  const api = useApi();
  const { data } = useQuery<{
    telemetry_ready: boolean;
    summary: { cost_usd: number; calls: number; average_cost_per_day_usd: number; average_cost_per_call_usd: number } | null;
  }>({
    queryKey: ['admin-cost-snapshot'],
    queryFn: async () => (await api.get('/admin/costs', { params: { days: 30 } })).data,
    staleTime: 30_000,
    retry: 0,
  });

  if (!data?.telemetry_ready || !data.summary) return null;
  const s = data.summary;
  const money = (value: number) => `$${value.toFixed(value < 0.01 ? 5 : 2)}`;
  return (
    <section style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>Cost snapshot</h2>
          <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '4px 0 0' }}>Last 30 days · successful calls recorded by TrueBrief</p>
        </div>
        <Link href="/admin/costs" style={{ fontSize: 12, color: 'var(--tb-green-dark)' }}>See all history</Link>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <StatCard label="Recorded cost" value={money(s.cost_usd)} />
        <StatCard label="Successful calls" value={s.calls.toLocaleString()} />
        <StatCard label="Average / day" value={money(s.average_cost_per_day_usd)} />
        <StatCard label="Average / call" value={money(s.average_cost_per_call_usd)} />
      </div>
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
            href="/admin/costs"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'var(--color-background-secondary)',
              border: '0.5px solid var(--color-border-secondary)',
              borderRadius: 8, padding: '7px 14px',
              fontSize: 13, color: 'var(--color-text-primary)',
              cursor: 'pointer', textDecoration: 'none',
            }}
          >
            <DollarSign size={13} />
            Costs and usage
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

      <FreezeToggle />
      <KeyStatusPanel />
      <QuotaAlertsBanner />
      <CostSnapshot />

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
        <RunRowList runs={data!.recent_runs} />
      </section>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
