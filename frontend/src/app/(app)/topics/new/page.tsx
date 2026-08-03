'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useApi } from '@/lib/useApi';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUp, Clock } from 'lucide-react';
import { getTimezone, localToUtc, utcToLocal, fmtHM, tzShortLabel, type ScheduleTime } from '@/lib/timezone';

// ── Types ──────────────────────────────────────────────────────────────────

// V5 (docs/core/architecture_v5.md §7): scan cadence is manual alarm-clock times.
// Times can now be set HERE at creation (stored as local component state, converted
// to UTC and PUT to the topic right after it's created — there's no topic id to attach
// a schedule to before that POST resolves) or left as the default and changed later
// from the topic page, which has the server-backed version of this same picker.
//
// The Quick/Standard/Thorough "coverage" picker that used to sit in the action bar was
// removed here: its value was never sent to the API (pure decoration), and its options
// described V4's source layers — "Scans RSS feeds and Tavily", "Adds Brave Search and
// Exa" — none of which exist in V5, where collection is a single Gemini Search call.

const STATIC_PILLS = [
  { label: 'Tech & AI',   fill: 'AI regulation' },
  { label: 'Finance',     fill: 'Fed rates' },
  { label: 'Geopolitics', fill: 'China Taiwan' },
  { label: 'Science',     fill: 'GLP-1 drugs' },
  { label: 'Startups',    fill: 'startup funding' },
];

interface SharedTopic { id: string; name: string; subscriber_count: number; }

// Shape of an axios error, narrowed by hand so we don't pull axios types into a page.
interface ApiErrorShape {
  response?: {
    status?: number;
    data?: { detail?: unknown };
    headers?: Record<string, unknown>;
  };
}

/** "90" -> "about 2 minutes" (rounded up), for the 429 retry-after hint. */
function formatWait(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} seconds`;
  const mins = Math.ceil(seconds / 60);
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'}`;
  const hrs = Math.ceil(mins / 60);
  return `${hrs} hour${hrs === 1 ? '' : 's'}`;
}

/**
 * Turn a failed POST /topics into an honest message.
 *
 * This used to be a single "Failed to create topic. Are you signed in?" for every
 * non-402 failure, which sent us chasing a phantom auth bug while the real cause was
 * a CORS preflight rejection (no `err.response` at all). Never collapse distinct
 * failures into one guess again.
 */
function describeCreateError(err: unknown): { message: string; status: number | null } {
  const res = (err as ApiErrorShape)?.response;

  // No response object at all -> the request never completed: network down, DNS,
  // or a CORS preflight the browser refused to hand back to JS.
  if (!res) {
    return { message: "Couldn't reach TrueBrief. Check your connection and try again.", status: null };
  }

  const status = res.status;
  const detail = typeof res.data?.detail === 'string' ? res.data.detail : null;

  let msg: string;
  if (status === 401 || status === 403) {
    msg = 'Your session expired. Please sign in again.';
  } else if (status === 429) {
    const raw = res.headers?.['retry-after'] ?? res.headers?.['Retry-After'];
    const secs = raw == null ? NaN : parseInt(String(raw), 10);
    msg = Number.isFinite(secs) && secs > 0
      ? `Too many topics created in the last hour. Try again in about ${formatWait(secs)}.`
      : 'Too many topics created in the last hour. Try again shortly.';
  } else if (status === 400) {
    msg = detail || "That topic couldn't be created. Try rewording it.";
  } else if (typeof status === 'number' && status >= 500) {
    msg = "TrueBrief's server had a problem creating this topic. Try again in a moment.";
  } else {
    msg = detail || 'Failed to create topic.';
  }

  return { message: msg, status: typeof status === 'number' ? status : null };
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function NewTopicPage() {
  const router = useRouter();
  const api = useApi();
  const qc = useQueryClient();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [nudge, setNudge] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [shellFocused, setShellFocused] = useState(false);
  // Schedule (UTC pairs). Empty = leave the default (once/day) — same server meaning
  // as an empty times[] on the topic-page picker.
  const [customTimes, setCustomTimes] = useState<ScheduleTime[]>([]);
  const [showSchedule, setShowSchedule] = useState(false);
  const [newTimeInput, setNewTimeInput] = useState('09:00');
  const scheduleRef = useRef<HTMLDivElement>(null);
  const tz = getTimezone();

  useEffect(() => {
    if (!showSchedule) return;
    const onClick = (e: MouseEvent) => {
      if (scheduleRef.current && !scheduleRef.current.contains(e.target as Node)) setShowSchedule(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [showSchedule]);

  const addCustomTime = () => {
    const [hStr, mStr] = newTimeInput.split(':');
    const localHour = parseInt(hStr, 10);
    const localMinute = parseInt(mStr, 10);
    if (Number.isNaN(localHour) || Number.isNaN(localMinute)) return;
    const utc = localToUtc(localHour, localMinute, tz);
    if (customTimes.some(t => t.hour === utc.hour && t.minute === utc.minute)) return;
    setCustomTimes([...customTimes, utc].sort((a, b) => a.hour * 60 + a.minute - (b.hour * 60 + b.minute)));
  };

  const removeCustomTime = (t: ScheduleTime) => {
    setCustomTimes(customTimes.filter(x => !(x.hour === t.hour && x.minute === t.minute)));
  };

  const localTimes = customTimes.map(t => utcToLocal(t.hour, t.minute, tz));
  const scheduleLabel = localTimes.length === 0
    ? 'Default (daily)'
    : localTimes.length <= 2
      ? localTimes.map(l => fmtHM(l.hour, l.minute)).join(', ')
      : `${localTimes.length} times/day`;

  // Debounce the query for search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Auto-resize textarea
  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
  }, []);
  useEffect(() => { autoResize(); }, [query, autoResize]);

  // Search shared topics when 2+ chars typed
  const { data: sharedTopics = [] } = useQuery<SharedTopic[]>({
    queryKey: ['shared-topics', debouncedQuery],
    queryFn: async () => {
      if (debouncedQuery.length < 2) return [];
      const r = await api.get(`/shared-topics?q=${encodeURIComponent(debouncedQuery)}`);
      return r.data;
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 10_000,
  });

  const handleSubmit = async () => {
    const q = query.trim();
    if (!q || submitting) return;
    setSubmitting(true);
    setError(null);
    setErrorStatus(null);
    setNudge(false);
    try {
      const res = await api.post('/topics', { raw_query: q });
      // Custom times set before submit -> apply now. No topic id exists until this
      // POST resolves, so this can't happen any earlier; an empty list here just
      // means "leave the default (once/day)" and nothing needs to be sent.
      if (customTimes.length > 0) {
        try {
          await api.put(`/topics/${res.data.id}/schedule`, { times: customTimes });
        } catch {
          // Topic creation already succeeded — a failed schedule PUT shouldn't block
          // navigation. The topic page's own picker (server-backed) covers retrying.
        }
      }
      await qc.invalidateQueries({ queryKey: ['topics'] });
      // Store the first scan task_id so the topic page can show the progress bar
      if (res.data.scan_task_id) {
        localStorage.setItem(`scan_task_${res.data.id}`, res.data.scan_task_id);
      }
      router.push(`/topics/${res.data.id}`);
    } catch (err: unknown) {
      console.error('POST /topics failed', err);
      const status = (err as ApiErrorShape)?.response?.status;
      if (status === 402) {
        setNudge(true);
      } else {
        const { message, status: code } = describeCreateError(err);
        setError(message);
        setErrorStatus(code);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const fillAndFocus = (text: string) => {
    setQuery(text);
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  // Pill style — split border to avoid shorthand conflict
  const pillBase: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '3px 9px', borderRadius: 20, cursor: 'pointer', fontSize: 12,
    borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'var(--color-border-secondary)',
    background: 'transparent', color: 'var(--color-text-secondary)', fontFamily: 'inherit',
  };

  const showSearchPills = debouncedQuery.length >= 2 && sharedTopics.length > 0;
  const pills = showSearchPills
    ? sharedTopics.map(t => ({ label: t.name, fill: t.name, isShared: true }))
    : STATIC_PILLS.map(p => ({ ...p, isShared: false }));

  // Highlight matched portion of text
  function highlight(text: string, q: string): React.ReactNode {
    if (!q || q.length < 2) return text;
    const idx = text.toLowerCase().indexOf(q.toLowerCase());
    if (idx === -1) return text;
    return <>{text.slice(0, idx)}<strong style={{ fontWeight: 600, color: '#085041' }}>{text.slice(idx, idx + q.length)}</strong>{text.slice(idx + q.length)}</>;
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 24px 44px' }}>
      <p style={{ fontSize: 22, fontWeight: 500, color: 'var(--color-text-primary)', textAlign: 'center', marginBottom: 24, margin: '0 0 24px' }}>
        What&apos;s worth your attention?
      </p>

      {/* Input shell */}
      <div
        style={{
          width: '100%', maxWidth: 420, borderRadius: 22,
          borderWidth: '0.5px', borderStyle: 'solid',
          borderColor: shellFocused ? '#0F6E56' : 'var(--color-border-secondary)',
          background: 'var(--color-background-primary)',
          transition: 'border-color 0.2s',
        }}
      >
        <textarea
          ref={textareaRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setShellFocused(true)}
          onBlur={() => setShellFocused(false)}
          placeholder="Tell me what to watch... e.g. Apple, Fed rates, EU AI regulation"
          rows={1}
          style={{
            width: '100%', display: 'block',
            padding: '14px 18px 10px', border: 'none', outline: 'none', resize: 'none',
            fontSize: 14, color: 'var(--color-text-primary)', background: 'transparent',
            minHeight: 52, maxHeight: 100, lineHeight: 1.6,
            fontFamily: 'inherit', boxSizing: 'border-box',
          }}
        />
        {/* Action bar */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 5,
          padding: '7px 10px', borderTop: '0.5px solid var(--color-border-tertiary)',
        }}>
          <div ref={scheduleRef} style={{ position: 'relative', marginRight: 'auto' }}>
            <button
              type="button"
              onClick={() => setShowSchedule(v => !v)}
              style={{ ...pillBase, ...(showSchedule || customTimes.length > 0 ? { borderColor: '#0F6E56', background: '#E1F5EE', color: '#085041' } : {}) }}
            >
              <Clock size={11} />{scheduleLabel}
            </button>
            {showSchedule && (
              <div style={{
                position: 'absolute', bottom: '100%', left: 0, marginBottom: 6, zIndex: 50,
                background: 'var(--color-background-primary)',
                border: '0.5px solid var(--color-border-secondary)',
                borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                minWidth: 240, padding: 10,
              }}>
                <p style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--color-text-tertiary)', margin: '0 0 8px' }}>
                  Scheduled run times · {tzShortLabel(tz)}
                </p>
                {customTimes.length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '0 0 10px' }}>
                    Default — once a day at {(() => { const l = utcToLocal(9, 0, tz); return fmtHM(l.hour, l.minute); })()}.
                    Add a time below to set your own schedule.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                    {localTimes.map((l, i) => (
                      <span
                        key={`${customTimes[i].hour}:${customTimes[i].minute}`}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          fontSize: 11, fontWeight: 500, color: 'var(--color-text-primary)',
                          background: 'var(--color-background-secondary)',
                          padding: '3px 6px 3px 8px', borderRadius: 12,
                        }}
                      >
                        {fmtHM(l.hour, l.minute)}
                        <button
                          type="button"
                          onClick={() => removeCustomTime(customTimes[i])}
                          title="Remove this time"
                          style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--color-text-tertiary)', fontSize: 13, lineHeight: 1, padding: 0, display: 'flex' }}
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
                    type="button"
                    onClick={addCustomTime}
                    style={{
                      fontSize: 12, fontWeight: 500, color: 'var(--tb-green)',
                      background: 'none', border: '0.5px solid var(--tb-green)',
                      borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
                    }}
                  >
                    Add
                  </button>
                </div>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !query.trim()}
            aria-label="Track this topic"
            style={{
              width: 30, height: 30, borderRadius: '50%', border: 'none', flexShrink: 0,
              background: query.trim() ? 'var(--color-text-primary)' : 'var(--color-border-secondary)',
              cursor: query.trim() ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => { if (query.trim()) (e.currentTarget as HTMLButtonElement).style.background = '#0F6E56'; }}
            onMouseLeave={e => { if (query.trim()) (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-text-primary)'; }}
          >
            <ArrowUp size={13} color={query.trim() ? 'var(--color-background-primary)' : 'var(--color-text-tertiary)'} />
          </button>
        </div>
      </div>

      {/* Error / nudge */}
      {error && (
        <p style={{ fontSize: 12, color: '#B91C1C', textAlign: 'center', marginTop: 10, maxWidth: 420 }}>
          {error}
          {errorStatus !== null && (
            <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', marginLeft: 5 }}>
              (HTTP {errorStatus})
            </span>
          )}
        </p>
      )}
      {nudge && (
        <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'center', marginTop: 10, maxWidth: 420 }}>
          Private topics need Pro. Follow a shared topic below (free), or{' '}
          <span style={{ color: 'var(--color-text-info)', cursor: 'pointer', textDecoration: 'underline' }}>upgrade</span>.
        </p>
      )}

      {/* Suggestion pills */}
      <div style={{
        width: '100%', maxWidth: 420, marginTop: 14,
        display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'center',
      }}>
        {pills.map(pill => (
          <button
            key={pill.label}
            type="button"
            onClick={() => fillAndFocus(pill.fill)}
            style={{
              padding: '5px 11px', borderRadius: 20, cursor: 'pointer',
              borderWidth: '0.5px', borderStyle: 'solid', borderColor: '#A3D9C5',
              background: '#F0FAF6', fontSize: 12, color: 'var(--color-text-primary)',
              fontFamily: 'inherit', display: 'inline-flex', alignItems: 'center', gap: 5,
              transition: 'background 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => {
              const b = e.currentTarget as HTMLButtonElement;
              b.style.background = '#D7F3E9'; b.style.borderColor = '#5DCAA5';
            }}
            onMouseLeave={e => {
              const b = e.currentTarget as HTMLButtonElement;
              b.style.background = '#F0FAF6'; b.style.borderColor = '#A3D9C5';
            }}
          >
            {showSearchPills ? highlight(pill.label, debouncedQuery) : pill.label}
            {pill.isShared && (
              <span style={{ fontSize: 10, background: '#0F6E56', color: '#fff', padding: '1px 5px', borderRadius: 8, fontWeight: 500 }}>
                Free
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
