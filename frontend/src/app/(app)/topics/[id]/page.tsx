'use client';

import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useCallback, useEffect, useMemo, useRef, use, useState } from 'react';
import { Clock, ScanSearch } from 'lucide-react';
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

// ── Schedule picker (V5 manual alarm-clock scheduling, docs/core/architecture_v5.md §7) ──
// Replaces the old Auto/Slow/Medium/Fast/Ultra-Fast interval picker: the user sets
// specific daily run times (UTC) instead of a polling interval AYR used to manage.

interface ScheduleTime { hour: number; minute: number }
interface ScheduleResponse { times: ScheduleTime[]; is_default: boolean }

function fmtScheduleTime(t: ScheduleTime): string {
  return `${String(t.hour).padStart(2, '0')}:${String(t.minute).padStart(2, '0')}`;
}

function scheduleButtonLabel(schedule: ScheduleResponse | undefined): string {
  if (!schedule || schedule.is_default) return 'Auto';
  if (schedule.times.length === 0) return 'Auto';
  if (schedule.times.length <= 2) return schedule.times.map(fmtScheduleTime).join(', ');
  return `${fmtScheduleTime(schedule.times[0])} +${schedule.times.length - 1}`;
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

function formatTime(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch { return ''; }
}

// ── Brief panel ──────────────────────────────────────────────────────────────
// The Briefer runs on every V5 scan and its output is what the 2026-07-26 benchmark
// actually scored (30/31 vs a plain Gemini ask) — but nothing rendered it, so users
// only ever saw the raw fact list. This surfaces it above the timeline.

interface BriefRow { id: string; content: string; delivered_at: string }

interface BriefBullet { text: string; sources: { domain: string; url: string }[] }
type BriefBlock =
  | { kind: 'lede'; text: string }
  | { kind: 'badge'; text: string }
  | { kind: 'section'; text: string }
  | { kind: 'bullet'; bullet: BriefBullet };

// Brief markdown shape (see src/truebrief/llm/prompts.py build_briefer_prompt):
//   📋 TrueBrief | Topic | Date        <- dropped, the page header already says this
//   **📌 Bottom line:** ...
//   🆕 NEW STORIES (N)  /  📈 UPDATES (N)
//   ━━━━━━━                            <- dropped, we draw a real border instead
//   **Section Title**
//   • Bullet text. → Sources: [domain.com](url), [other.com](url)
export function parseBrief(md: string): BriefBlock[] {
  const out: BriefBlock[] = [];
  for (const raw of md.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('📋') || /^[━─-]{3,}$/.test(line)) continue;

    const lede = line.match(/^\*\*📌\s*Bottom line:?\*\*\s*(.+)$/i);
    if (lede) { out.push({ kind: 'lede', text: lede[1].trim() }); continue; }

    if (/^(🆕|📈|⚠️)/.test(line)) { out.push({ kind: 'badge', text: line }); continue; }

    if (/^\*\*.+\*\*$/.test(line)) {
      out.push({ kind: 'section', text: line.replace(/^\*\*|\*\*$/g, '').trim() });
      continue;
    }

    if (/^[•\-*]\s+/.test(line)) {
      const body = line.replace(/^[•\-*]\s+/, '');
      const [textPart, srcPart] = body.split(/\s*→\s*Sources:\s*/i);
      const sources: { domain: string; url: string }[] = [];
      if (srcPart) {
        for (const m of srcPart.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)) {
          sources.push({ domain: m[1], url: m[2] });
        }
      }
      out.push({ kind: 'bullet', bullet: { text: textPart.trim(), sources } });
    }
  }
  return out;
}

function BriefPanel({ topicId }: { topicId: string }) {
  const api = useApi();
  const [open, setOpen] = useState(true);
  const { data } = useQuery<BriefRow[]>({
    queryKey: ['topic-briefs', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/briefs`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const latest = data?.[0];
  const blocks = useMemo(() => (latest ? parseBrief(latest.content) : []), [latest]);
  if (!latest || blocks.length === 0) return null;

  return (
    <div style={{
      margin: '12px 22px 4px', padding: '14px 16px',
      border: '1px solid var(--color-border-tertiary)', borderRadius: 12,
      background: 'var(--color-background-primary)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{
          fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: 'var(--color-text-secondary)',
        }}>
          Latest brief
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10.5, color: 'var(--color-text-tertiary)' }}>
            {timeAgo(latest.delivered_at)}
          </span>
          <button
            onClick={() => setOpen((v) => !v)}
            style={{
              fontSize: 11, color: 'var(--color-text-secondary)', background: 'none',
              border: '0.5px solid var(--color-border-secondary)', borderRadius: 6,
              padding: '1px 7px', cursor: 'pointer',
            }}
          >
            {open ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>

      {open && (
        <div style={{ marginTop: 10 }}>
          {blocks.map((b, i) => {
            if (b.kind === 'lede') {
              return (
                <p key={i} style={{
                  fontSize: 14, lineHeight: 1.6, color: 'var(--color-text-primary)',
                  margin: '0 0 12px', fontWeight: 500,
                }}>
                  {b.text}
                </p>
              );
            }
            if (b.kind === 'badge') {
              return (
                <div key={i} style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.04em',
                  color: 'var(--color-text-secondary)',
                  margin: '14px 0 8px', paddingTop: 10,
                  borderTop: '0.5px solid var(--color-border-tertiary)',
                }}>
                  {b.text}
                </div>
              );
            }
            if (b.kind === 'section') {
              return (
                <div key={i} style={{
                  fontSize: 12.5, fontWeight: 600, color: 'var(--color-text-primary)',
                  margin: '10px 0 5px',
                }}>
                  {b.text}
                </div>
              );
            }
            return (
              <div key={i} style={{ display: 'flex', gap: 7, margin: '0 0 7px' }}>
                <span style={{ color: 'var(--color-text-tertiary)', flexShrink: 0 }}>•</span>
                <div>
                  <span style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--color-text-primary)' }}>
                    {b.bullet.text}
                  </span>
                  {b.bullet.sources.length > 0 && (
                    <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 5, marginLeft: 7, verticalAlign: 'middle' }}>
                      {b.bullet.sources.map((s, j) => (
                        <SourceChip key={j} domain={s.domain} url={s.url} />
                      ))}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
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
          <span
            title={`Confirmed by ${fact.verified_count} independent sources (only the primary source link is stored)`}
            style={{
              fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-tertiary)',
              background: 'var(--color-background-tertiary)', borderRadius: 5, padding: '1px 6px',
            }}
          >
            ✓ {fact.verified_count} sources
          </span>
        )}
        {fact.first_seen_at && (
          <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', opacity: 0.7 }}>
            {formatTime(fact.first_seen_at)}
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

  const timeline = data?.timeline ?? [];

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

  return (
    <div style={{ padding: '8px 22px 48px' }}>
      <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', margin: '4px 0 6px' }}>
        {(() => { const c = data?.fact_count ?? 0; return c >= 600 ? `${c}+` : c; })()} facts · newest first
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
            {group.facts.map((f, i) => (
              <HistoryFactRow fact={f} key={f.id ?? i} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Scan progress bar ──────────────────────────────────────────────────────

// V5 stages (pipeline/v5_runner.py): one grounded Gemini search, then extraction,
// then memory/dedup, then the brief. The old V4 wording ("Collecting articles…",
// "Reading sources…") described the deleted scrape/harvest chain and no longer
// matches anything the backend does.
const SCAN_STEPS = [
  'Searching the web…',
  'Reading what changed…',
  'Extracting the facts…',
  'Checking against what you already know…',
  'Filtering out repeats…',
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
        {/* Fill is full-width and scaled on the X axis rather than width-animated:
            the parent ticks every 250ms for the whole scan, and transform stays on
            the compositor instead of forcing a layout pass on each tick. */}
        <div style={{
          height: '100%', width: '100%', borderRadius: 2,
          background: 'var(--tb-green)',
          transform: `scaleX(${progress / 100})`,
          transformOrigin: 'left center',
          transition: isDone ? 'transform 0.4s ease' : 'transform 0.25s linear',
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
  const [showFreqPicker, setShowFreqPicker] = useState(false);
  const [newTimeInput, setNewTimeInput] = useState('09:00');
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const freqRef = useRef<HTMLDivElement>(null);

  // Close schedule picker on outside click
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

  const { data: schedule } = useQuery<ScheduleResponse>({
    queryKey: ['topic-schedule', id],
    queryFn: async () => (await api.get(`/topics/${id}/schedule`)).data,
    staleTime: 30_000,
  });

  const { mutate: updateSchedule, isPending: isUpdatingFreq } = useMutation({
    mutationFn: (times: ScheduleTime[]) =>
      api.put(`/topics/${id}/schedule`, { times }),
    onSuccess: () => {
      setScheduleError(null);
      qc.invalidateQueries({ queryKey: ['topic-schedule', id] });
      qc.invalidateQueries({ queryKey: ['topic', id] });
      qc.invalidateQueries({ queryKey: ['topics'] });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setScheduleError(detail || 'Could not update schedule');
      setTimeout(() => setScheduleError(null), 5000);
    },
  });

  const addScheduleTime = () => {
    const [hStr, mStr] = newTimeInput.split(':');
    const hour = parseInt(hStr, 10);
    const minute = parseInt(mStr, 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) return;
    const current = schedule && !schedule.is_default ? schedule.times : [];
    if (current.some(t => t.hour === hour && t.minute === minute)) return;
    updateSchedule([...current, { hour, minute }].sort((a, b) => a.hour * 60 + a.minute - (b.hour * 60 + b.minute)));
  };

  const removeScheduleTime = (t: ScheduleTime) => {
    const current = (schedule?.times ?? []).filter(x => !(x.hour === t.hour && x.minute === t.minute));
    updateSchedule(current);
  };

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
    qc.invalidateQueries({ queryKey: ['topic-briefs', id] });
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
                title="Change scheduled scan times"
                style={{
                  fontSize: 10, borderWidth: '0.5px', borderStyle: 'solid',
                  borderColor: showFreqPicker ? 'var(--color-border-primary)' : 'var(--color-border-secondary)',
                  color: 'var(--color-text-secondary)', padding: '1px 6px', borderRadius: 10,
                  background: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 3,
                  opacity: isUpdatingFreq ? 0.5 : 1,
                }}
              >
                {scheduleButtonLabel(schedule)}
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none" style={{ marginLeft: 1 }}>
                  <path d="M1 2.5L4 5.5L7 2.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                </svg>
              </button>
              {showFreqPicker && (
                <div style={{
                  position: 'absolute', top: '100%', right: 0, marginTop: 4, zIndex: 50,
                  background: 'var(--color-background-primary)',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  minWidth: 240, padding: 10,
                }}>
                  <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--color-text-tertiary)', margin: '0 0 8px' }}>
                    Scheduled run times (UTC)
                  </p>
                  {schedule?.is_default ? (
                    <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '0 0 10px' }}>
                      Auto — once a day at {schedule.times[0] ? fmtScheduleTime(schedule.times[0]) : '09:00'}.
                      Add a time below to set your own schedule.
                    </p>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                      {(schedule?.times ?? []).map(t => (
                        <span
                          key={`${t.hour}:${t.minute}`}
                          style={{
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                            fontSize: 11, fontWeight: 500, color: 'var(--color-text-primary)',
                            background: 'var(--color-background-secondary)',
                            padding: '3px 6px 3px 8px', borderRadius: 12,
                          }}
                        >
                          {fmtScheduleTime(t)}
                          <button
                            onClick={() => removeScheduleTime(t)}
                            disabled={isUpdatingFreq}
                            title="Remove this time"
                            style={{
                              border: 'none', background: 'none', cursor: 'pointer',
                              color: 'var(--color-text-tertiary)', fontSize: 13, lineHeight: 1,
                              padding: 0, display: 'flex',
                            }}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input
                      type="time"
                      value={newTimeInput}
                      onChange={(e) => setNewTimeInput(e.target.value)}
                      style={{
                        fontSize: 12, padding: '4px 6px', borderRadius: 6,
                        border: '0.5px solid var(--color-border-secondary)',
                        background: 'var(--color-background-primary)',
                        color: 'var(--color-text-primary)', flex: 1,
                      }}
                    />
                    <button
                      onClick={addScheduleTime}
                      disabled={isUpdatingFreq}
                      style={{
                        fontSize: 12, fontWeight: 500, color: 'var(--tb-green)',
                        background: 'none', border: '0.5px solid var(--tb-green)',
                        borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
                        opacity: isUpdatingFreq ? 0.5 : 1,
                      }}
                    >
                      Add
                    </button>
                  </div>
                  {scheduleError && (
                    <p style={{ fontSize: 11, color: '#B45309', margin: '8px 0 0' }}>{scheduleError}</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content — synthesized brief (what the benchmark scored) over the full
          alpha + context timeline. Story mode removed for V5 (never proven better
          than the plain feed; reintroduce post-production only if proven). */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <BriefPanel topicId={id} />
        <HistoryView topicId={id} />
      </div>
    </div>
  );
}
