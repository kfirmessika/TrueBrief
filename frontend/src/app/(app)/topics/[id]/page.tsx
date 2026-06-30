'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useCallback, useEffect, useRef, use, useState } from 'react';
import { ChevronDown, Clock, ScanSearch } from 'lucide-react';
import { useScanStatus, useTriggerScan } from '@/hooks/useTopics';

// ── Types ──────────────────────────────────────────────────────────────────

interface Topic {
  id: string;
  raw_query: string;
  frequency: string;
  last_scan_at: string | null;
  is_scanning?: boolean;
}

// IC7 — state-of-play topic header
type SopStatus = 'agreed' | 'contested' | 'postponed' | 'escalating';
interface StateOfPlayThread {
  label: string;
  status: SopStatus;
  note?: string;
}
interface StateOfPlay {
  situation?: string;
  threads: StateOfPlayThread[];
  updated_at?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function formatDayLabel(ymd: string): string {
  const [y, m, d] = ymd.split('-').map(Number);
  if (!y || !m || !d) return ymd;
  const dt = new Date(y, m - 1, d);
  const now = new Date();
  const sameYear = dt.getFullYear() === now.getFullYear();
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }) });
}

// ── Significance weights (mirrors IC2 in runner.py) ───────────────────────

const CLASS_WEIGHT: Record<string, number> = {
  state_change: 6, escalation: 5, development: 4,
  incremental: 3, tally: 2, routine: 1,
};

const CLASS_DOT: Record<string, string> = {
  state_change: '#1A7A52',
  escalation: '#B42318',
};

// ── KnownFact type (richer, returned by updated /known-facts endpoint) ────

interface KnownFact {
  source_domain: string;
  source_url: string | null;
  alpha_text: string;
  first_seen_at: string;
  contradiction_note?: string | null;
  context?: string | null;
  event_class?: string | null;
  event_date?: string | null;
  verified_count?: number;
}

// ── FactRowTopic — plain-text fact row with inline accordion ──────────────

function FactRowTopic({ fact }: { fact: KnownFact }) {
  const [expanded, setExpanded] = useState(false);
  const dotColor = fact.event_class ? CLASS_DOT[fact.event_class] : undefined;
  const ago = (() => {
    if (!fact.first_seen_at) return '';
    const diff = Date.now() - new Date(fact.first_seen_at).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`;
    return `${Math.floor(h / 24)}d`;
  })();
  const domain = fact.source_domain;
  const href = fact.source_url ?? (domain ? `https://${domain}` : undefined);
  const hasContext = !!fact.context;

  return (
    <div style={{ padding: '11px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <div
        onClick={() => hasContext && setExpanded(e => !e)}
        style={{ cursor: hasContext ? 'pointer' : 'default', display: 'flex', alignItems: 'flex-start', gap: 8 }}
      >
        <span style={{
          marginTop: 7, width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
          background: dotColor ?? 'var(--color-border-secondary)',
        }} />
        <p style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--color-text-primary)', margin: 0, flex: 1 }}>
          {fact.alpha_text}
        </p>
        {hasContext && (
          <ChevronDown
            size={13}
            color="var(--color-text-tertiary)"
            style={{ flexShrink: 0, marginTop: 5, transition: 'transform 0.15s', transform: expanded ? 'rotate(180deg)' : 'none' }}
          />
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, paddingLeft: 13 }}>
        {domain && <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{domain}</span>}
        {domain && ago && <span style={{ fontSize: 12, color: 'var(--color-border-secondary)' }}>·</span>}
        {ago && <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{ago}</span>}
        {(fact.verified_count ?? 0) > 1 && (
          <><span style={{ fontSize: 12, color: 'var(--color-border-secondary)' }}>·</span>
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{fact.verified_count} sources</span></>
        )}
        {fact.contradiction_note && (
          <><span style={{ fontSize: 12, color: 'var(--color-border-secondary)' }}>·</span>
          <span title={`Disputed — ${fact.contradiction_note}`} style={{
            fontSize: 11, fontWeight: 600, color: '#B45309', cursor: 'help',
          }}>⚠️ Disputed</span></>
        )}
      </div>
      {expanded && fact.context && (
        <div style={{ marginTop: 8, paddingLeft: 13 }}>
          <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: '0 0 6px' }}>
            {fact.context}
          </p>
          {href && (
            <a href={href} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 12, color: 'var(--tb-green)', textDecoration: 'none' }}>
              View source →
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ── RecentFactsView — Brief tab content ───────────────────────────────────

function RecentFactsView({ topicId }: { topicId: string }) {
  const api = useApi();
  const { data: facts = [], isLoading } = useQuery<KnownFact[]>({
    queryKey: ['topic-known-facts', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/known-facts`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const sevenDaysAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const oneDayAgo = Date.now() - 24 * 3600 * 1000;

  const scored = facts
    .filter(f => !f.first_seen_at || new Date(f.first_seen_at).getTime() > sevenDaysAgo)
    .map(f => {
      const lagHours = f.first_seen_at
        ? (Date.now() - new Date(f.first_seen_at).getTime()) / 3600000
        : 999;
      const weight = CLASS_WEIGHT[f.event_class ?? ''] ?? 2;
      return { ...f, score: weight * Math.exp(-lagHours / 36) };
    })
    .sort((a, b) => b.score - a.score);

  const recentFacts = scored.filter(f => !f.first_seen_at || new Date(f.first_seen_at).getTime() > oneDayAgo);
  const earlierFacts = scored.filter(f => f.first_seen_at && new Date(f.first_seen_at).getTime() <= oneDayAgo);

  const sectionLabel = (text: string) => (
    <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.10em', textTransform: 'uppercase', color: 'var(--color-text-tertiary)', padding: '14px 0 2px' }}>
      {text}
    </div>
  );

  if (isLoading) {
    return (
      <div style={{ padding: '8px 22px' }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ padding: '10px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
            <div style={{ height: 14, width: `${70 + i * 6}%`, background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 11, width: '25%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
          </div>
        ))}
      </div>
    );
  }

  if (scored.length === 0) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 14, color: 'var(--color-text-tertiary)', margin: 0 }}>
          Run a scan to start tracking facts.
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 22px 48px' }}>
      {recentFacts.length > 0 && (
        <>
          {sectionLabel('Recent')}
          {recentFacts.map((f, i) => <FactRowTopic key={i} fact={f} />)}
        </>
      )}
      {earlierFacts.length > 0 && (
        <>
          {sectionLabel('Earlier this week')}
          {earlierFacts.map((f, i) => <FactRowTopic key={i} fact={f} />)}
        </>
      )}
    </div>
  );
}

// ── State of play (IC7) ──────────────────────────────────────────────────────

const SOP_STATUS: Record<SopStatus, { icon: string; color: string; bg: string }> = {
  agreed:     { icon: '✅', color: '#1A7A52', bg: '#E6F5EE' },
  contested:  { icon: '⚠️', color: '#B45309', bg: '#FBF1E6' },
  postponed:  { icon: '⏸', color: '#2B5FA5', bg: '#EEF3FB' },
  escalating: { icon: '🔺', color: '#B42318', bg: '#FBEAE8' },
};

function StateOfPlayBlock({ sop }: { sop: StateOfPlay | null }) {
  if (!sop || (!sop.situation && (!sop.threads || sop.threads.length === 0))) return null;
  return (
    <div style={{
      background: 'var(--color-background-primary)',
      border: '1px solid var(--color-border-tertiary)',
      borderRadius: 12, padding: '14px 18px', margin: '16px 0 8px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
        color: 'var(--color-text-tertiary)', marginBottom: 8,
      }}>
        State of play
      </div>
      {sop.situation && (
        <p style={{ fontSize: 14, color: 'var(--color-text-primary)', lineHeight: 1.55, margin: '0 0 10px', fontWeight: 500 }}>
          {sop.situation}
        </p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {(sop.threads ?? []).map((t, i) => {
          const s = SOP_STATUS[t.status] ?? SOP_STATUS.contested;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 13 }}>
              <span style={{ flexShrink: 0 }}>{s.icon}</span>
              <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>{t.label}</span>
              <span style={{
                flexShrink: 0, fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,
                background: s.bg, color: s.color, textTransform: 'capitalize',
              }}>
                {t.status}
              </span>
              {t.note && (
                <span style={{ color: 'var(--color-text-tertiary)', fontSize: 12 }}>· {t.note}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── History view ─────────────────────────────────────────────────────────────

interface HistoryFact {
  text: string;
  context: string | null;
  event_class: string | null;
  event_date: string | null;
  first_seen_at: string | null;
  source_domain: string | null;
  source_url: string | null;
  verified_count: number;
  contradiction_note: string | null;
}
interface HistoryGroup { date: string; facts: HistoryFact[]; }
interface HistoryDoc { built_at?: string; fact_count?: number; timeline: HistoryGroup[]; }

// Only high-signal classes get a chip; routine/tally/incremental stay quiet.
const CLASS_CHIP: Record<string, { label: string; color: string; bg: string }> = {
  state_change: { label: 'Milestone', color: '#1A7A52', bg: '#E6F5EE' },
  escalation:   { label: 'Escalation', color: '#B42318', bg: '#FBEAE8' },
};

function HistoryFactRow({ fact }: { fact: HistoryFact }) {
  const chip = fact.event_class ? CLASS_CHIP[fact.event_class] : undefined;
  const domain = fact.source_domain ?? undefined;
  const favicon = domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=32` : null;
  return (
    <div style={{ position: 'relative', paddingLeft: 22, paddingBottom: 16 }}>
      {/* timeline marker */}
      <span style={{
        position: 'absolute', left: 0, top: 5, width: 9, height: 9, borderRadius: '50%',
        background: chip ? chip.color : 'var(--color-border-secondary)',
        boxShadow: chip ? `0 0 0 3px ${chip.bg}` : 'none',
      }} />
      <p style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--color-text-primary)', margin: 0 }}>
        {fact.text}
      </p>
      {fact.context && (
        <p style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
          {fact.context}
        </p>
      )}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
        {chip && (
          <span style={{
            fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20,
            background: chip.bg, color: chip.color,
          }}>
            {chip.label}
          </span>
        )}
        {domain && (
          <a href={fact.source_url ?? `https://${domain}`} target="_blank" rel="noopener noreferrer"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11,
              color: 'var(--color-text-secondary)', textDecoration: 'none',
              border: '1px solid var(--color-border-secondary)', borderRadius: 5, padding: '1px 6px 1px 4px',
            }}>
            {favicon && <img src={favicon} alt={domain} width={11} height={11} style={{ borderRadius: 2 }}
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />}
            {domain}
          </a>
        )}
        {fact.verified_count > 1 && (
          <span title={`${fact.verified_count} independent sources`} style={{
            fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-tertiary)',
            background: 'var(--color-background-tertiary)', borderRadius: 5, padding: '1px 6px',
          }}>
            {fact.verified_count} sources
          </span>
        )}
        {fact.contradiction_note && (
          <span title={`Disputed — ${fact.contradiction_note}`} style={{
            fontSize: 10.5, fontWeight: 600, color: '#B45309',
            background: '#FBF1E6', border: '1px solid #F3D9B8', borderRadius: 5, padding: '1px 6px', cursor: 'help',
          }}>
            ⚠️ Disputed
          </span>
        )}
      </div>
    </div>
  );
}

function HistoryView({ topicId }: { topicId: string }) {
  const api = useApi();
  const { data, isLoading } = useQuery<HistoryDoc>({
    queryKey: ['topic-history', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/history`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  if (isLoading) {
    return (
      <div style={{ padding: '24px 22px' }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ marginBottom: 14, paddingLeft: 22 }}>
            <div style={{ height: 12, width: '85%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 11, width: '60%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
          </div>
        ))}
      </div>
    );
  }

  const timeline = data?.timeline ?? [];
  if (timeline.length === 0) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 14, color: 'var(--color-text-tertiary)', margin: 0 }}>
          No history yet. Run a scan to start the timeline.
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '8px 22px 48px' }}>
      <div style={{
        fontSize: 11, color: 'var(--color-text-tertiary)', margin: '4px 0 14px',
      }}>
        {data?.fact_count ?? 0} facts · the story so far, newest first
      </div>
      {timeline.map(group => (
        <div key={group.date} style={{ marginBottom: 8 }}>
          <div style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
            color: 'var(--color-text-secondary)', margin: '6px 0 10px',
          }}>
            {formatDayLabel(group.date)}
          </div>
          {/* vertical timeline rail */}
          <div style={{ position: 'relative' }}>
            <div style={{
              position: 'absolute', left: 4, top: 4, bottom: 8, width: 1,
              background: 'var(--color-border-tertiary)',
            }} />
            {group.facts.map((f, i) => <HistoryFactRow key={i} fact={f} />)}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Scan progress bar ──────────────────────────────────────────────────────

const SCAN_STEPS = [
  'Searching the web…',
  'Collecting articles…',
  'Reading sources…',
  'Filtering relevant content…',
  'Analyzing what matters…',
  'Connecting the dots…',
  'Writing your brief…',
  'Almost done…',
];

function ScanProgressBar({ topicId, taskId, active, onDone }: { topicId: string; taskId: string | null; active: boolean; onDone: () => void }) {
  const { data: status } = useScanStatus(taskId, topicId);
  const [stepIdx, setStepIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const calledDone = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const taskState = status?.state;
  const taskDone = taskState === 'SUCCESS' || taskState === 'FAILURE';
  const isDone = taskId ? taskDone : active === false;

  useEffect(() => {
    if (isDone) {
      setProgress(100);
      if (!calledDone.current) {
        calledDone.current = true;
        const t = setTimeout(() => {
          localStorage.removeItem(`scan_task_${topicId}`);
          onDoneRef.current();
        }, 800);
        return () => clearTimeout(t);
      }
      return;
    }

    const stepTimer = setInterval(() => {
      setStepIdx(i => Math.min(i + 1, SCAN_STEPS.length - 2));
    }, 4000);

    const progressTimer = setInterval(() => {
      setProgress(p => {
        if (p >= 90) return p + 0.3;
        return p + (90 - p) * 0.04;
      });
    }, 200);

    return () => { clearInterval(stepTimer); clearInterval(progressTimer); };
  }, [isDone, topicId]);

  const displayStep = isDone ? 'Done!' : SCAN_STEPS[stepIdx];
  const cappedProgress = Math.min(progress, isDone ? 100 : 90);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap', minWidth: 170 }}>
        {displayStep}
      </span>
      <div style={{ flex: 1, height: 3, borderRadius: 2, background: 'var(--color-border-secondary)', overflow: 'hidden', maxWidth: 160 }}>
        <div style={{
          height: '100%', borderRadius: 2,
          background: 'var(--tb-green)',
          width: `${cappedProgress}%`,
          transition: isDone ? 'width 0.4s ease' : 'width 0.2s linear',
        }} />
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function TopicViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const api = useApi();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<'brief' | 'history'>('brief');
  const [scanError, setScanError] = useState<string | null>(null);

  const { mutate: triggerScan, isPending: isScanPending } = useTriggerScan();

  const handleScanNow = () => {
    if (isScanPending || scanTaskId) return;
    setScanError(null);
    triggerScan(id, {
      onSuccess: (data) => {
        if (data?.task_id) {
          localStorage.setItem(`scan_task_${id}`, data.task_id);
          setScanTaskId(data.task_id);
        }
      },
      onError: (err: unknown) => {
        const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status;
        if (status === 429) {
          const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '';
          const hoursMatch = detail.match(/(\d+(?:\.\d+)?)\s*hour/i);
          const msg = hoursMatch
            ? `Next scan in ${Math.ceil(parseFloat(hoursMatch[1]))}h`
            : 'Rate limit reached';
          setScanError(msg);
          setTimeout(() => setScanError(null), 5000);
        } else {
          setScanError('Scan failed');
          setTimeout(() => setScanError(null), 4000);
        }
      },
    });
  };

  const [scanTaskId, setScanTaskId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(`scan_task_${id}`);
  });

  const handleScanDone = useCallback(() => {
    setScanTaskId(null);
    qc.invalidateQueries({ queryKey: ['topic', id] });
    qc.invalidateQueries({ queryKey: ['topic-known-facts', id] });
    qc.invalidateQueries({ queryKey: ['topic-state-of-play', id] });
    qc.invalidateQueries({ queryKey: ['topic-history', id] });
    qc.invalidateQueries({ queryKey: ['feed'] });
    qc.invalidateQueries({ queryKey: ['topics'] });
  }, [qc, id]);

  // §8 — viewing a topic advances its delta anchor
  useEffect(() => {
    api.post('/feed/seen', { topic_ids: [id] })
      .then(() => qc.invalidateQueries({ queryKey: ['feed', 'live'] }))
      .catch(() => {});
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll localStorage every 500ms to catch scan tasks set by the sidebar
  useEffect(() => {
    const check = () => {
      const id_ = localStorage.getItem(`scan_task_${id}`);
      setScanTaskId(prev => prev !== id_ ? id_ : prev);
    };
    check();
    const interval = setInterval(check, 500);
    window.addEventListener('storage', check);
    return () => { clearInterval(interval); window.removeEventListener('storage', check); };
  }, [id]);

  const { data: topic } = useQuery<Topic>({
    queryKey: ['topic', id],
    queryFn: async () => (await api.get(`/topics/${id}`)).data,
    staleTime: 0,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    refetchInterval: (q) => {
      const d = q.state.data as Topic | undefined;
      const localTask = typeof window !== 'undefined' && !!localStorage.getItem(`scan_task_${id}`);
      return (d?.is_scanning || localTask) ? 3_000 : 60_000;
    },
  });

  const { data: stateOfPlay = null } = useQuery<StateOfPlay | null>({
    queryKey: ['topic-state-of-play', id],
    queryFn: async () => (await api.get(`/topics/${id}/state-of-play`)).data?.state_of_play ?? null,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const scanning = !!scanTaskId || !!topic?.is_scanning;

  // Suppress unused-import warnings from formatDate/formatTime (used by HistoryFactRow indirectly)
  void formatDate;
  void formatTime;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sticky header */}
      <div style={{
        background: 'var(--color-background-primary)',
        padding: '16px 22px 12px',
        borderBottom: '0.5px solid var(--color-border-tertiary)',
        flexShrink: 0,
      }}>
        <p style={{ fontSize: 17, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
          {topic?.raw_query ?? '…'}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <Clock size={11} color="var(--color-text-tertiary)" />
          {scanning ? (
            <ScanProgressBar topicId={id} taskId={scanTaskId} active={topic?.is_scanning ?? false} onDone={handleScanDone} />
          ) : (
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
              Last scanned {timeAgo(topic?.last_scan_at ?? null)}
            </span>
          )}
          {!scanning && (
            <button
              onClick={handleScanNow}
              disabled={isScanPending}
              title="Run a new scan"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                fontSize: 11, color: isScanPending ? 'var(--color-text-tertiary)' : 'var(--tb-green)',
                background: 'none', border: 'none', cursor: isScanPending ? 'default' : 'pointer',
                padding: '1px 4px', borderRadius: 4,
                opacity: isScanPending ? 0.5 : 1,
              }}
            >
              <ScanSearch size={11} />
              {isScanPending ? 'Starting…' : 'Scan now'}
            </button>
          )}
          {scanError && (
            <span style={{ fontSize: 11, color: '#B45309' }}>{scanError}</span>
          )}
          {topic?.frequency && (
            <span style={{
              fontSize: 10, borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'var(--color-border-secondary)',
              color: 'var(--color-text-secondary)', padding: '1px 6px', borderRadius: 10,
            }}>
              {topic.frequency}
            </span>
          )}
        </div>

        {/* Tab bar — Brief + History only (Stories paused: V3_PAUSE_STORY_GRAPH) */}
        <div style={{ display: 'flex', gap: 4, marginTop: 12, borderBottom: '0.5px solid var(--color-border-tertiary)', paddingBottom: 0 }}>
          {(['brief', 'history'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: 12, fontWeight: activeTab === tab ? 600 : 400,
                color: activeTab === tab ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                padding: '4px 10px 8px',
                borderBottom: activeTab === tab ? '2px solid var(--tb-green)' : '2px solid transparent',
                marginBottom: -1,
                textTransform: 'capitalize',
                transition: 'color 0.1s',
              }}
            >
              {tab === 'brief' ? 'Brief' : 'History'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {activeTab === 'history' ? (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <HistoryView topicId={id} />
        </div>
      ) : (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* IC7 — state-of-play status board */}
          {stateOfPlay && (
            <div style={{ padding: '0 22px' }}>
              <StateOfPlayBlock sop={stateOfPlay} />
            </div>
          )}
          <RecentFactsView topicId={id} />
        </div>
      )}
    </div>
  );
}
