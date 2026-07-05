'use client';

import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useCallback, useEffect, useMemo, useRef, use, useState } from 'react';
import { Clock, ScanSearch, BookOpen, List } from 'lucide-react';
import { useScanStatus, useTriggerScan } from '@/hooks/useTopics';
import { SourceChip } from '@/components/SourceChip';

// ── Types ──────────────────────────────────────────────────────────────────

interface Topic {
  id: string;
  raw_query: string;
  frequency: string;
  poll_interval_seconds?: number | null;
  last_scan_at: string | null;
  is_scanning?: boolean;
}

// ── Frequency picker ───────────────────────────────────────────────────────

const FREQ_OPTS: { label: string; seconds: number | null; desc: string }[] = [
  { label: 'Auto',       seconds: null,  desc: 'TrueBrief adjusts speed based on activity' },
  { label: 'Slow',       seconds: 86400, desc: 'Once a day — quiet topics, low quota use' },
  { label: 'Medium',     seconds: 21600, desc: 'Every 6 hours' },
  { label: 'Fast',       seconds: 3600,  desc: 'Every hour' },
  { label: 'Ultra Fast', seconds: 900,   desc: 'Every 15 min — breaks news, high quota use' },
];

function intervalToLabel(s: number | null | undefined): string {
  if (!s) return 'Auto';
  if (s >= 86400) return 'Slow';
  if (s >= 21600) return 'Medium';
  if (s >= 3600)  return 'Fast';
  return 'Ultra Fast';
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

function formatDayLabel(ymd: string): string {
  const [y, m, d] = ymd.split('-').map(Number);
  if (!y || !m || !d) return ymd;
  const dt = new Date(y, m - 1, d);
  const now = new Date();
  const sameYear = dt.getFullYear() === now.getFullYear();
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }) });
}

// ── History view ─────────────────────────────────────────────────────────────

interface HistoryFact {
  id?: string | null;
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
        {(fact.source_domain || fact.source_url) && (
          <SourceChip domain={fact.source_domain} url={fact.source_url} />
        )}
        {fact.verified_count > 1 && (
          <span title={`${fact.verified_count} independent sources`} style={{
            fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-tertiary)',
            background: 'var(--color-background-tertiary)', borderRadius: 5, padding: '1px 6px',
          }}>
            +{fact.verified_count - 1} more
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

// A connective-tissue bridge between two adjacent alphas (story mode).
function StoryConnector({ text }: { text: string }) {
  if (!text) return null;
  return (
    <div style={{ paddingLeft: 22, paddingBottom: 14, marginTop: -8 }}>
      <p style={{
        fontSize: 12.5, fontStyle: 'italic', lineHeight: 1.5,
        color: 'var(--color-text-tertiary)', margin: 0,
        borderLeft: '2px solid var(--color-border-secondary)', paddingLeft: 10,
      }}>
        {text}
      </p>
    </div>
  );
}

function HistoryView({ topicId, storyMode }: { topicId: string; storyMode: boolean }) {
  const api = useApi();
  const { data, isLoading } = useQuery<HistoryDoc>({
    queryKey: ['topic-history', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/history`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const timeline = data?.timeline ?? [];

  // Flatten in display order (newest first) so alphas keep identical positions in
  // both modes — story just inserts a bridge between adjacent rows.
  const flat = useMemo(() => timeline.flatMap((g) => g.facts), [timeline]);
  const N = flat.length;

  // Story connectors: the backend links chronological pairs (oldest→newest). We send
  // chronological order and map each connector back into the newest-first display.
  const chronoTexts = useMemo(() => flat.map((f) => f.text).reverse(), [flat]);
  const chronoIds = useMemo(() => {
    const ids = flat.map((f) => f.id ?? null).reverse();
    return ids.every(Boolean) ? (ids as string[]) : null;
  }, [flat]);
  const { data: storyData, isFetching: storyFetching } = useQuery<{ connectors: string[] }>({
    queryKey: ['topic-story', topicId, N],
    queryFn: async () =>
      (await api.post(`/topics/${topicId}/story`, { facts: chronoTexts, ...(chronoIds && { fact_ids: chronoIds }) }, { timeout: 20_000 })).data,
    enabled: storyMode && N >= 2,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
  const connectors = storyData?.connectors ?? [];

  // The bridge shown BELOW display row i (between i and the older i+1). See mapping note.
  const connectorBelow = (displayIdx: number): string => {
    if (!storyMode || displayIdx >= N - 1) return '';
    return connectors[N - 2 - displayIdx] ?? '';
  };

  if (isLoading) {
    return (
      <div style={{ padding: '24px 22px' }}>
        {[1, 2, 3].map((i) => (
          <div key={i} style={{ marginBottom: 14, paddingLeft: 22 }}>
            <div style={{ height: 12, width: '85%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 11, width: '60%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
          </div>
        ))}
      </div>
    );
  }

  if (timeline.length === 0) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 14, color: 'var(--color-text-tertiary)', margin: 0 }}>
          No history yet. Run a scan to start the timeline.
        </p>
      </div>
    );
  }

  let gi = -1; // running global display index across all groups
  return (
    <div style={{ padding: '8px 22px 48px' }}>
      <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', margin: '4px 0 14px' }}>
        {data?.fact_count ?? 0} facts · {storyMode ? 'the story so far' : 'newest first'}
        {storyMode && storyFetching && ' · weaving…'}
      </div>
      {timeline.map((group) => (
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
            {group.facts.map((f, i) => {
              gi += 1;
              const bridge = connectorBelow(gi);
              return (
                <div key={i}>
                  <HistoryFactRow fact={f} />
                  {bridge && <StoryConnector text={bridge} />}
                </div>
              );
            })}
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

// Progress is derived from a persisted start timestamp (localStorage), NOT from local
// component state — so leaving and returning to the topic page continues the bar
// smoothly instead of resetting it to 0 on every remount.
function ScanProgressBar({ topicId, taskId, active, onDone }: { topicId: string; taskId: string | null; active: boolean; onDone: () => void }) {
  const { data: status } = useScanStatus(taskId, topicId);
  const [start, setStart] = useState<number | null>(null);
  const [now, setNow] = useState<number>(0);
  const calledDone = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const startKey = `scan_start_${topicId}`;

  const taskState = status?.state;
  const taskDone = taskState === 'SUCCESS' || taskState === 'FAILURE';
  const isDone = taskId ? taskDone : active === false;

  // Establish (or reuse) the persisted start timestamp on mount.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let s = localStorage.getItem(startKey);
    if (!s) { s = String(Date.now()); localStorage.setItem(startKey, s); }
    setStart(Number(s));
    setNow(Date.now());
  }, [startKey]);

  // Tick while running.
  useEffect(() => {
    if (isDone) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [isDone]);

  // Completion → clean up both keys, then notify parent.
  useEffect(() => {
    if (!isDone || calledDone.current) return;
    calledDone.current = true;
    const t = setTimeout(() => {
      localStorage.removeItem(`scan_task_${topicId}`);
      localStorage.removeItem(startKey);
      onDoneRef.current();
    }, 800);
    return () => clearTimeout(t);
  }, [isDone, topicId, startKey]);

  const elapsed = start ? Math.max(now - start, 0) / 1000 : 0; // seconds
  // Asymptotic to 90% (half-life ~20s); jumps to 100% on done.
  const timed = 90 * (1 - Math.pow(0.5, elapsed / 20));
  const progress = isDone ? 100 : Math.min(timed, 90);
  const stepIdx = isDone
    ? SCAN_STEPS.length - 1
    : Math.min(Math.floor(elapsed / 5), SCAN_STEPS.length - 2);
  const displayStep = isDone ? 'Done!' : SCAN_STEPS[stepIdx];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap', minWidth: 170 }}>
        {displayStep}
      </span>
      <div style={{ flex: 1, height: 3, borderRadius: 2, background: 'var(--color-border-secondary)', overflow: 'hidden', maxWidth: 160 }}>
        <div style={{
          height: '100%', borderRadius: 2,
          background: 'var(--tb-green)',
          width: `${progress}%`,
          transition: isDone ? 'width 0.4s ease' : 'width 0.25s linear',
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

  const [scanError, setScanError] = useState<string | null>(null);
  const [storyMode, setStoryMode] = useState(false);
  const [showFreqPicker, setShowFreqPicker] = useState(false);
  const freqRef = useRef<HTMLDivElement>(null);

  // Close frequency picker on outside click
  useEffect(() => {
    if (!showFreqPicker) return;
    const handler = (e: MouseEvent) => {
      if (freqRef.current && !freqRef.current.contains(e.target as Node)) {
        setShowFreqPicker(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showFreqPicker]);

  const { mutate: updateFreq, isPending: isUpdatingFreq } = useMutation({
    mutationFn: (seconds: number | null) =>
      api.patch(`/topics/${id}/frequency`, { poll_interval_seconds: seconds }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topic', id] });
      qc.invalidateQueries({ queryKey: ['topics'] });
      setShowFreqPicker(false);
    },
  });

  const { mutate: triggerScan, isPending: isScanPending } = useTriggerScan();

  const handleScanNow = () => {
    if (isScanPending || scanTaskId) return;
    setScanError(null);
    triggerScan(id, {
      onSuccess: (data) => {
        if (data?.task_id) {
          localStorage.setItem(`scan_task_${id}`, data.task_id);
          localStorage.setItem(`scan_start_${id}`, String(Date.now()));
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
    qc.invalidateQueries({ queryKey: ['topic-history', id] });
    qc.invalidateQueries({ queryKey: ['topic-story', id] });
    qc.invalidateQueries({ queryKey: ['feed'] });
    qc.invalidateQueries({ queryKey: ['topics'] });
  }, [qc, id]);

  // §8 — viewing a topic advances its delta anchor
  useEffect(() => {
    api.post('/feed/seen', { topic_ids: [id] })
      .then(() => qc.invalidateQueries({ queryKey: ['feed'] }))
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

  const scanning = !!scanTaskId || !!topic?.is_scanning;

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
          {topic && (
            <div ref={freqRef} style={{ position: 'relative' }}>
              <button
                onClick={() => setShowFreqPicker(v => !v)}
                disabled={isUpdatingFreq}
                title="Change scan frequency"
                style={{
                  fontSize: 10, borderWidth: '0.5px', borderStyle: 'solid',
                  borderColor: showFreqPicker ? 'var(--color-border-primary)' : 'var(--color-border-secondary)',
                  color: 'var(--color-text-secondary)', padding: '1px 6px', borderRadius: 10,
                  background: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 3,
                  opacity: isUpdatingFreq ? 0.5 : 1,
                }}
              >
                {intervalToLabel(topic.poll_interval_seconds)}
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none" style={{ marginLeft: 1 }}>
                  <path d="M1 2.5L4 5.5L7 2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
              </button>
              {showFreqPicker && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50,
                  background: 'var(--color-background-primary)',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  minWidth: 220, overflow: 'hidden',
                }}>
                  {FREQ_OPTS.map(opt => {
                    const current = intervalToLabel(topic.poll_interval_seconds);
                    const isActive = opt.label === current;
                    return (
                      <button
                        key={opt.label}
                        onClick={() => updateFreq(opt.seconds)}
                        style={{
                          display: 'block', width: '100%', textAlign: 'left',
                          padding: '8px 12px', border: 'none', cursor: 'pointer',
                          background: isActive ? 'var(--color-background-secondary)' : 'transparent',
                          borderBottom: '0.5px solid var(--color-border-tertiary)',
                        }}
                      >
                        <span style={{ fontSize: 12, fontWeight: isActive ? 500 : 400, color: 'var(--color-text-primary)', display: 'block' }}>
                          {opt.label}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
                          {opt.desc}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content — raw alpha timeline (skeleton); Story button weaves connectors between them */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', padding: '12px 22px 0' }}>
          <button
            onClick={() => setStoryMode((s) => !s)}
            title={storyMode ? 'Show raw alphas' : 'Weave the alphas into a story'}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 11, fontWeight: 600,
              color: storyMode ? 'var(--tb-green)' : 'var(--color-text-secondary)',
              background: storyMode ? 'var(--color-background-tertiary)' : 'transparent',
              border: '1px solid var(--color-border-secondary)', borderRadius: 8,
              padding: '4px 10px', cursor: 'pointer',
            }}
          >
            {storyMode ? <List size={12} /> : <BookOpen size={12} />}
            {storyMode ? 'Raw alphas' : 'Story'}
          </button>
        </div>
        <HistoryView topicId={id} storyMode={storyMode} />
      </div>
    </div>
  );
}
