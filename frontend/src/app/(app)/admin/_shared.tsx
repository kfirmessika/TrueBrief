'use client';

/**
 * Small pieces shared across the admin tab screens (Overview, Topics, Users,
 * per-user drill-down). Extracted from admin/page.tsx rather than duplicated —
 * the per-user drill-down needs the exact same "recent runs" row rendering and
 * stat-tile styling admin/page.tsx already has. Inline CSS-var styles, matching
 * the app-shell/admin styling convention (never Tailwind here).
 */

import Link from 'next/link';

// Raw pipeline_run.exit_status / llm_call_log.stage values, for a founder-facing label
// instead of the internal snake_case name. Anything not listed here still renders —
// this is cosmetic, not a whitelist.
export const STAGE_LABELS: Record<string, string> = {
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
export const STATUS_LABELS: Record<string, string> = {
  success: 'Success', running: 'Running', error: 'Error',
  no_update: 'No new facts', failure: 'Failure',
};
export const STATUS_COLOR: Record<string, string> = {
  success: 'var(--tb-green-dark)', running: 'var(--tb-amber)',
  error: '#DC2626', failure: '#DC2626', no_update: 'var(--color-text-tertiary)',
};

// Founder-facing labels for llm_call_log stage names / model ids, reused from
// STAGE_LABELS above where the key matches; falls back to the raw string.
export function stepLabel(step: string): string {
  return STAGE_LABELS[step] ?? step;
}

export function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
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

export function StatusBadge({ status }: { status: string | null }) {
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

// Row shape shared by GET /admin/metrics.recent_runs and GET /admin/users/{id}.recent_runs —
// both serialize pipeline_run the same way (see routes.py). topic_name is only present on
// the per-user drill-down (metrics doesn't join topic names), so it's optional here.
export interface AdminRunRow {
  id: string;
  topic_id: string | null;
  topic_name?: string;
  started_at: string | null;
  duration_s: number | null;
  exit_status: string | null;
  new: number;
  update: number;
  dupe: number;
  error: string | null;
}

export function RunRow({ run, first }: { run: AdminRunRow; first?: boolean }) {
  return (
    <Link href={`/admin/runs/${run.id}`} style={{
      display: 'grid', gridTemplateColumns: '1fr 80px 70px 70px 70px 70px auto',
      alignItems: 'center', gap: 12,
      padding: '10px 16px', textDecoration: 'none',
      borderTop: first ? 'none' : '0.5px solid var(--color-border-tertiary)',
    }}>
      <div>
        <div style={{ fontSize: 12, color: 'var(--color-text-primary)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {run.topic_name ?? run.topic_id ?? '—'}
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
  );
}

export function RunRowList({ runs, emptyLabel = 'No runs yet.' }: { runs: AdminRunRow[]; emptyLabel?: string }) {
  return (
    <div style={{
      background: 'var(--color-background-secondary)',
      border: '0.5px solid var(--color-border-secondary)',
      borderRadius: 10, overflow: 'hidden',
    }}>
      {runs.length === 0 && (
        <div style={{ padding: '16px', fontSize: 13, color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
          {emptyLabel}
        </div>
      )}
      {runs.map((run, i) => (
        <RunRow key={run.id} run={run} first={i === 0} />
      ))}
    </div>
  );
}
