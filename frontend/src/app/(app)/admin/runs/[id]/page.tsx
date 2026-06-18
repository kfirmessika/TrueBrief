'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { use, useState } from 'react';
import Link from 'next/link';
import { ChevronRight, ChevronDown, AlertCircle, ArrowLeft, Sparkles } from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

interface RunSummary {
  id: string;
  topic_id: string | null;
  topic_name: string;
  started_at: string | null;
  duration_s: number | null;
  exit_status: string | null;
  brief_length: number;
  articles_collected: number;
  articles_selected: number;
  alphas_extracted: number;
  new: number;
  update: number;
  dupe: number;
  error: string | null;
  llm_calls: number;
  llm_cost_usd: number;
}

interface TimelineEvent {
  kind: 'stage' | 'llm';
  seq: number;
  stage: string | null;
  label?: string | null;
  data?: Record<string, unknown>;
  // llm-only
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  duration_ms?: number;
  system_prompt?: string | null;
  prompt?: string | null;
  response?: string | null;
  created_at?: string | null;
}

interface RunTrace {
  run: RunSummary;
  timeline: TimelineEvent[];
}

// ── Stage styling ─────────────────────────────────────────────────────────────

const STAGE_COLORS: Record<string, string> = {
  start: '#64748B',
  query: '#6366F1',
  collect: '#0EA5E9',
  dedup: '#475569',
  mmr: '#8B5CF6',
  harvest: '#10B981',
  relevance: '#F59E0B',
  judge: '#EC4899',
  brief: '#3B82F6',
  error: '#DC2626',
  llm: '#7C3AED',
};

function stageColor(ev: TimelineEvent): string {
  if (ev.kind === 'llm') return STAGE_COLORS.llm;
  return STAGE_COLORS[ev.stage ?? ''] ?? '#64748B';
}

// ── Small UI helpers ──────────────────────────────────────────────────────────

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-secondary)',
      borderRadius: 10, padding: '12px 14px',
    }}>
      <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
      <div style={{ fontSize: 19, fontWeight: 600, color: 'var(--color-text-primary)', lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

function PromptBlock({ title, text, accent }: { title: string; text: string; accent?: string }) {
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: accent ?? 'var(--color-text-tertiary)', marginBottom: 4 }}>
        {title}
      </div>
      <pre style={{
        margin: 0, padding: '10px 12px', maxHeight: 320, overflow: 'auto',
        background: 'var(--color-background-tertiary)',
        border: '0.5px solid var(--color-border-tertiary)', borderRadius: 8,
        fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-secondary)',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      }}>{text}</pre>
    </div>
  );
}

// Render a structured-trace data payload in a readable way.
function StageData({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, v]) => v !== null && v !== undefined && v !== '');
  if (entries.length === 0) return null;

  const longText = new Set(['why', 'reason', 'traceback', 'brief_preview', 'reasoning']);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {entries.map(([key, value]) => {
        // Long explanatory strings → callout block
        if (typeof value === 'string' && (longText.has(key) || value.length > 120)) {
          return <PromptBlock key={key} title={key} text={value} />;
        }
        // Arrays → list
        if (Array.isArray(value)) {
          return (
            <div key={key}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)', margin: '4px 0' }}>
                {key} ({value.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {value.slice(0, 30).map((item, i) => (
                  <div key={i} style={{
                    fontSize: 12, color: 'var(--color-text-secondary)',
                    padding: '5px 9px', background: 'var(--color-background-tertiary)',
                    borderRadius: 6, border: '0.5px solid var(--color-border-tertiary)',
                  }}>
                    {typeof item === 'object' && item !== null
                      ? <ObjectRow obj={item as Record<string, unknown>} />
                      : String(item)}
                  </div>
                ))}
              </div>
            </div>
          );
        }
        // Scalars → key: value line
        return (
          <div key={key} style={{ display: 'flex', gap: 8, fontSize: 12 }}>
            <span style={{ color: 'var(--color-text-tertiary)', minWidth: 130, fontFamily: 'ui-monospace, monospace' }}>{key}</span>
            <span style={{ color: 'var(--color-text-primary)', wordBreak: 'break-word' }}>{String(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function ObjectRow({ obj }: { obj: Record<string, unknown> }) {
  // Compact inline rendering of an object (e.g. an article or a fact)
  const title = (obj.title ?? obj.text ?? obj.alpha_text ?? obj.query_text) as string | undefined;
  const url = obj.url as string | undefined;
  const meta = Object.entries(obj)
    .filter(([k]) => !['title', 'text', 'alpha_text', 'query_text', 'url'].includes(k))
    .map(([k, v]) => `${k}=${v}`)
    .join('  ·  ');
  return (
    <div>
      {title && <div style={{ color: 'var(--color-text-primary)' }}>{title}</div>}
      {url && (
        <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-accent, #3B82F6)', fontSize: 11, wordBreak: 'break-all' }}>
          {url}
        </a>
      )}
      {meta && <div style={{ color: 'var(--color-text-tertiary)', fontSize: 11, marginTop: 2, fontFamily: 'ui-monospace, monospace' }}>{meta}</div>}
    </div>
  );
}

// ── Timeline event card ───────────────────────────────────────────────────────

function EventCard({ ev, index }: { ev: TimelineEvent; index: number }) {
  const [open, setOpen] = useState(false);
  const color = stageColor(ev);
  const isLlm = ev.kind === 'llm';
  const badge = isLlm ? `AI · ${ev.stage}` : ev.stage ?? 'stage';

  return (
    <div style={{
      borderLeft: `3px solid ${color}`,
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-secondary)',
      borderLeftWidth: 3, borderRadius: 8, overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px', background: 'transparent', border: 'none',
          cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
        }}
      >
        <span style={{ color: 'var(--color-text-tertiary)', fontSize: 11, width: 22, fontVariantNumeric: 'tabular-nums' }}>{index + 1}</span>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 11, fontWeight: 600, color: '#fff', background: color,
          padding: '2px 8px', borderRadius: 5, textTransform: 'uppercase', letterSpacing: '0.04em',
          whiteSpace: 'nowrap',
        }}>
          {isLlm && <Sparkles size={11} />}
          {badge}
        </span>
        <span style={{ flex: 1, fontSize: 13, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {ev.label ?? (isLlm ? `${ev.model} · ${(ev.input_tokens ?? 0)}→${(ev.output_tokens ?? 0)} tok` : '')}
        </span>
        {isLlm && (
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
            ${(ev.cost_usd ?? 0).toFixed(6)}
          </span>
        )}
        {open ? <ChevronDown size={15} color="var(--color-text-tertiary)" /> : <ChevronRight size={15} color="var(--color-text-tertiary)" />}
      </button>

      {open && (
        <div style={{ padding: '4px 14px 14px 44px' }}>
          {isLlm ? (
            <>
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 11, color: 'var(--color-text-tertiary)', marginBottom: 4 }}>
                <span>model: <b style={{ color: 'var(--color-text-secondary)' }}>{ev.model}</b></span>
                <span>in: {ev.input_tokens ?? 0} tok</span>
                <span>out: {ev.output_tokens ?? 0} tok</span>
                <span>{ev.duration_ms ?? 0} ms</span>
                <span>${(ev.cost_usd ?? 0).toFixed(6)}</span>
              </div>
              {ev.system_prompt && <PromptBlock title="System prompt" text={ev.system_prompt} accent={color} />}
              {ev.prompt
                ? <PromptBlock title="Prompt (what we sent the AI)" text={ev.prompt} accent={color} />
                : <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 8, fontStyle: 'italic' }}>
                    Prompt not captured (TRACE_PIPELINE off or pre-012 schema).
                  </div>}
              {ev.response && <PromptBlock title="Response (what the AI returned)" text={ev.response} accent={color} />}
            </>
          ) : (
            ev.data && <StageData data={ev.data} />
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function RunTracePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const api = useApi();

  const { data, isLoading, isError, error } = useQuery<RunTrace>({
    queryKey: ['admin-run-trace', id],
    queryFn: async () => (await api.get(`/admin/runs/${id}`)).data,
    retry: 0,
  });

  if (isLoading) {
    return <div style={{ padding: 32, color: 'var(--color-text-secondary)', fontSize: 14 }}>Loading run trace…</div>;
  }

  if (isError) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    return (
      <div style={{ padding: 32, display: 'flex', alignItems: 'center', gap: 10, color: '#DC2626', fontSize: 14 }}>
        <AlertCircle size={18} />
        {status === 403 ? 'Access denied. Your account is not in ADMIN_USER_IDS.'
          : status === 404 ? 'Run not found.'
          : 'Failed to load run trace.'}
      </div>
    );
  }

  const r = data!.run;
  const statusColor = r.exit_status === 'success' ? 'var(--tb-green-dark, #15803D)'
    : r.exit_status === 'error' ? '#DC2626'
    : 'var(--color-text-secondary)';

  return (
    <div style={{ maxWidth: 980, margin: '0 auto', padding: '28px 24px' }}>
      <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--color-text-tertiary)', textDecoration: 'none', marginBottom: 18 }}>
        <ArrowLeft size={14} /> Back to admin
      </Link>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 19, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
          {r.topic_name}
        </h1>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, fontSize: 12, color: 'var(--color-text-tertiary)', flexWrap: 'wrap' }}>
          <span style={{ color: statusColor, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{r.exit_status ?? 'unknown'}</span>
          <span>{r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</span>
          <span>{r.duration_s != null ? `${r.duration_s}s` : '—'}</span>
          <span style={{ fontFamily: 'ui-monospace, monospace' }}>{r.id}</span>
        </div>
        {r.error && (
          <div style={{ marginTop: 10, padding: '10px 12px', background: '#FEE2E2', color: '#991B1B', borderRadius: 8, fontSize: 12, fontFamily: 'ui-monospace, monospace' }}>
            {r.error}
          </div>
        )}
      </div>

      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 10, marginBottom: 26 }}>
        <Stat label="Collected" value={r.articles_collected} sub="articles" />
        <Stat label="Selected" value={r.articles_selected} sub="via MMR" />
        <Stat label="Facts" value={r.alphas_extracted} sub="harvested" />
        <Stat label="New / Upd / Dup" value={`${r.new}/${r.update}/${r.dupe}`} />
        <Stat label="Brief" value={`${r.brief_length}`} sub="chars" />
        <Stat label="LLM calls" value={r.llm_calls} sub={`$${r.llm_cost_usd.toFixed(5)}`} />
      </div>

      {/* Timeline */}
      <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: 4 }}>
        Pipeline trace
      </h2>
      <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '0 0 14px' }}>
        Every stage in order — query &amp; tools chosen, what each source returned, MMR picks, the exact
        prompt/response of each AI call, and every per-fact judge decision. Click a row to expand.
      </p>

      {data!.timeline.length === 0 ? (
        <div style={{ padding: 16, fontSize: 13, color: 'var(--color-text-tertiary)', fontStyle: 'italic', background: 'var(--color-background-secondary)', borderRadius: 8 }}>
          No trace events recorded. This run predates the trace panel, or TRACE_PIPELINE was off / the
          012 migration hasn&apos;t been applied.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {data!.timeline.map((ev, i) => (
            <EventCard key={`${ev.kind}-${ev.seq}-${i}`} ev={ev} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
