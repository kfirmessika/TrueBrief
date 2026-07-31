'use client';

import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useCallback, useEffect, useMemo, useRef, use, useState } from 'react';
import { Clock, ScanSearch } from 'lucide-react';
import { useScanStatus, useTriggerScan } from '@/hooks/useTopics';
import { SourceChip } from '@/components/SourceChip';
import { getTimezone, utcToLocal, localToUtc, fmtHM, tzShortLabel, type ScheduleTime } from '@/lib/timezone';

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

interface ScheduleResponse { times: ScheduleTime[]; is_default: boolean }

/** A stored UTC schedule time, rendered in the viewer's own zone. */
function fmtScheduleTime(t: ScheduleTime, tz: string): string {
  const l = utcToLocal(t.hour, t.minute, tz);
  return fmtHM(l.hour, l.minute);
}

// The button used to read "Auto" whenever the topic was on the default schedule, which
// was a leftover from V4's AYR adaptive scheduler and no longer describes anything:
// V5 has no adaptive mode, the default is simply one run a day. Showing the actual
// time is both truthful and more useful than a word that implies a feature we removed.
function scheduleButtonLabel(schedule: ScheduleResponse | undefined, tz: string): string {
  if (!schedule || schedule.times.length === 0) return '—';
  if (schedule.times.length <= 2) return schedule.times.map((t) => fmtScheduleTime(t, tz)).join(', ');
  return `${fmtScheduleTime(schedule.times[0], tz)} +${schedule.times.length - 1}`;
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

// `lastRun` is the topic's last_scan_at, which the parent's ['topic', id] query polls
// every 60s. Including it in the query key is what makes this panel notice a
// SERVER-SIDE scheduled scan: without it the panel never refetched while the page sat
// open (no refetchInterval, and handleScanDone only fires for a scan you triggered
// yourself), so the header could read "last scan 0m ago" over a 2-day-old brief.
function BriefBody({ content }: { content: string }) {
  const blocks = useMemo(() => parseBrief(content), [content]);
  return (
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
  );
}

/** One collapsed past brief: date + lede preview, expands in place. */
function PastBriefRow({ brief }: { brief: BriefRow }) {
  const [open, setOpen] = useState(false);
  const lede = useMemo(() => {
    const l = parseBrief(brief.content).find((b) => b.kind === 'lede');
    return l && 'text' in l ? l.text : '';
  }, [brief.content]);

  return (
    <div style={{ borderTop: '0.5px solid var(--color-border-tertiary)', padding: '9px 0 2px' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex', alignItems: 'baseline', gap: 8, width: '100%', textAlign: 'left',
          background: 'none', border: 'none', padding: 0, cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
          {formatDayLabel(brief.delivered_at.slice(0, 10))} · {formatTime(brief.delivered_at)}
        </span>
        {!open && lede && (
          <span style={{
            fontSize: 12, color: 'var(--color-text-tertiary)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {lede}
          </span>
        )}
      </button>
      {open && <BriefBody content={brief.content} />}
    </div>
  );
}

function BriefPanel({ topicId, lastRun }: { topicId: string; lastRun?: string | null }) {
  const api = useApi();
  const [open, setOpen] = useState(true);
  const [showPast, setShowPast] = useState(false);
  const { data } = useQuery<BriefRow[]>({
    queryKey: ['topic-briefs', topicId, lastRun],
    queryFn: async () => (await api.get(`/topics/${topicId}/briefs`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  // Ordered newest-first by the API, and already filtered to V5-era briefs server-side
  // (config/settings.py V5_CUTOVER_DATE) — every scan's brief is kept, not just the last.
  const latest = data?.[0];
  const past = data?.slice(1) ?? [];
  if (!latest) return null;

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

      {open && <BriefBody content={latest.content} />}

      {past.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <button
            onClick={() => setShowPast((v) => !v)}
            style={{
              fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)',
              background: 'none', border: 'none', padding: '6px 0 0', cursor: 'pointer',
              borderTop: '0.5px solid var(--color-border-tertiary)', width: '100%', textAlign: 'left',
            }}
          >
            {showPast ? 'Hide' : 'Show'} {past.length} earlier brief{past.length === 1 ? '' : 's'}
          </button>
          {showPast && (
            <div style={{ marginTop: 4 }}>
              {past.map((b) => <PastBriefRow key={b.id} brief={b} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Raw per-fact timeline (HistoryView/HistoryFactRow) removed 2026-07-30 — user
// feedback: it looked bad next to the brief and duplicated the same facts less
// readably. BriefPanel above is now the entire content area.

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
  // Re-render when the zone changes in Settings (same tab fires 'tb-timezone-change';
  // another tab fires the native 'storage' event).
  const [tz, setTz] = useState(getTimezone);
  useEffect(() => {
    const sync = () => setTz(getTimezone());
    window.addEventListener('tb-timezone-change', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('tb-timezone-change', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);
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

  // The user types a time in their own zone; the API stores UTC.
  const addScheduleTime = () => {
    const [hStr, mStr] = newTimeInput.split(':');
    const localHour = parseInt(hStr, 10);
    const localMinute = parseInt(mStr, 10);
    if (Number.isNaN(localHour) || Number.isNaN(localMinute)) return;
    const { hour, minute } = localToUtc(localHour, localMinute, tz);
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
                {scheduleButtonLabel(schedule, tz)}
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
                    Scheduled run times · {tzShortLabel(tz)}
                  </p>
                  {schedule?.is_default ? (
                    <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '0 0 10px' }}>
                      Default — once a day at{' '}
                      {schedule.times[0] ? fmtScheduleTime(schedule.times[0], tz) : fmtScheduleTime({ hour: 9, minute: 0 }, tz)}.
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
                          {fmtScheduleTime(t, tz)}
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

      {/* Content — the synthesized brief only (what the benchmark scored). The raw
          fact-by-fact timeline was removed 2026-07-30 — user feedback: it "looks
          bad" next to the brief and duplicates the same information less readably.
          Story mode removed for V5 (never proven better than the plain feed;
          reintroduce post-production only if proven). */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <BriefPanel topicId={id} lastRun={topic?.last_scan_at} />
      </div>
    </div>
  );
}
