'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useApi } from '@/lib/useApi';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUp } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

// V5 (docs/core/architecture_v5.md §7): scan cadence is set via manual alarm-clock
// times on the topic page after creation, not at creation time — a new topic starts
// with the default (once/day) schedule automatically.
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
  const [shellFocused, setShellFocused] = useState(false);

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
    setNudge(false);
    try {
      const res = await api.post('/topics', { raw_query: q });
      await qc.invalidateQueries({ queryKey: ['topics'] });
      // Store the first scan task_id so the topic page can show the progress bar
      if (res.data.scan_task_id) {
        localStorage.setItem(`scan_task_${res.data.id}`, res.data.scan_task_id);
      }
      router.push(`/topics/${res.data.id}`);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 402) setNudge(true);
      else setError('Failed to create topic. Are you signed in?');
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
      {error && <p style={{ fontSize: 12, color: '#B91C1C', textAlign: 'center', marginTop: 10, maxWidth: 420 }}>{error}</p>}
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
