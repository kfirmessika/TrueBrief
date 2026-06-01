'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useApi } from '@/lib/useApi';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowUp, Clock, ScanLine, ChevronDown } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

type FrequencyOption = { label: string; badge: string; badgeStyle: string; tooltip?: string };
type CoverageOption  = { label: string; badge: string; badgeStyle: string; tooltip?: string };

const FREQUENCY_OPTIONS: FrequencyOption[] = [
  { label: 'Auto',            badge: 'Recommended', badgeStyle: 'recommended', tooltip: 'TrueBrief learns which sources update most for your topic and adjusts scan frequency automatically. No waste, no gaps.' },
  { label: 'Daily',           badge: 'Free',         badgeStyle: 'free' },
  { label: 'Hourly',          badge: 'Pro',          badgeStyle: 'pro', tooltip: 'Scans every hour. Best for fast-moving topics like earnings, politics, or live events.' },
  { label: 'Custom interval', badge: 'Pro',          badgeStyle: 'pro' },
];

const COVERAGE_OPTIONS: CoverageOption[] = [
  { label: 'Quick',     badge: 'Free',         badgeStyle: 'free' },
  { label: 'Standard',  badge: 'Recommended',  badgeStyle: 'recommended', tooltip: 'Scans RSS feeds and Tavily. Strong coverage for most topics at low cost.' },
  { label: 'Thorough',  badge: 'Pro',          badgeStyle: 'pro', tooltip: 'Adds Brave Search and Exa — scans a wider net including PDFs and less-indexed sources. Best for high-stakes topics.' },
];

const SUGGESTION_PILLS = [
  { label: 'Tech & AI',    fill: 'AI regulation' },
  { label: 'Finance',      fill: 'Fed rates' },
  { label: 'Geopolitics',  fill: 'China Taiwan' },
  { label: 'Science',      fill: 'GLP-1 drugs' },
  { label: 'Startups',     fill: 'startup funding' },
];

const BADGE_STYLES: Record<string, React.CSSProperties> = {
  recommended: {
    background: 'var(--color-background-secondary)',
    border: '0.5px solid var(--color-border-tertiary)',
    color: 'var(--color-text-tertiary)',
  },
  free: {
    background: 'var(--color-background-success)',
    color: 'var(--color-text-success)',
  },
  pro: {
    background: 'var(--color-background-info)',
    color: 'var(--color-text-info)',
  },
};

// ── Dropdown ───────────────────────────────────────────────────────────────

function DropdownPanel<T extends { label: string; badge: string; badgeStyle: string; tooltip?: string }>({
  options,
  selected,
  onSelect,
}: {
  options: T[];
  selected: string;
  onSelect: (label: string) => void;
}) {
  const [openTooltip, setOpenTooltip] = useState<string | null>(null);

  return (
    <div style={{
      width: '100%', maxWidth: 420, marginTop: 6,
      border: '0.5px solid var(--color-border-secondary)',
      borderRadius: 12, background: 'var(--color-background-primary)',
      overflow: 'hidden',
    }}>
      {options.map((opt, i) => (
        <div
          key={opt.label}
          onClick={() => onSelect(opt.label)}
          style={{
            padding: '10px 14px',
            borderBottom: i < options.length - 1 ? '0.5px solid var(--color-border-tertiary)' : 'none',
            background: selected === opt.label ? 'var(--color-background-secondary)' : 'transparent',
            cursor: 'pointer',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-background-secondary)'; }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLDivElement).style.background = selected === opt.label
              ? 'var(--color-background-secondary)' : 'transparent';
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)' }}>{opt.label}</span>
              {opt.tooltip && (
                <span
                  onClick={e => { e.stopPropagation(); setOpenTooltip(openTooltip === opt.label ? null : opt.label); }}
                  style={{ fontSize: 13, color: 'var(--color-text-tertiary)', cursor: 'pointer', lineHeight: 1 }}
                  title="info"
                >ⓘ</span>
              )}
            </div>
            <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 10, flexShrink: 0, ...BADGE_STYLES[opt.badgeStyle] }}>
              {opt.badge}
            </span>
          </div>
          {openTooltip === opt.label && opt.tooltip && (
            <div style={{
              marginTop: 5, fontSize: 11, background: 'var(--color-background-tertiary)',
              borderRadius: 8, padding: '5px 8px', color: 'var(--color-text-secondary)', lineHeight: 1.5,
            }}>
              {opt.tooltip}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function NewTopicPage() {
  const router = useRouter();
  const api = useApi();
  const qc = useQueryClient();

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [query, setQuery] = useState('');
  const [frequency, setFrequency] = useState('Auto');
  const [coverage, setCoverage] = useState('Standard');
  const [openPanel, setOpenPanel] = useState<'frequency' | 'coverage' | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [nudge, setNudge] = useState(false);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
  }, []);

  useEffect(() => { autoResize(); }, [query, autoResize]);

  const handleSubmit = async () => {
    const q = query.trim();
    if (!q) return;
    setSubmitting(true);
    try {
      const res = await api.post('/topics', { raw_query: q });
      await qc.invalidateQueries({ queryKey: ['topics'] });
      router.push(`/topics/${res.data.id}`);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 402) {
        setNudge(true);
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

  const fillSuggestion = (text: string) => {
    setQuery(text);
    textareaRef.current?.focus();
  };

  const togglePanel = (panel: 'frequency' | 'coverage') => {
    setOpenPanel(prev => prev === panel ? null : panel);
  };

  const pillBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '3px 9px', borderRadius: 20, cursor: 'pointer', fontSize: 12,
    border: '0.5px solid var(--color-border-secondary)',
    background: 'transparent', color: 'var(--color-text-secondary)',
    fontFamily: 'inherit',
  };

  const pillActive: React.CSSProperties = {
    borderColor: '#0F6E56',
    background: '#E1F5EE',
    color: '#085041',
  };

  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', padding: '60px 24px 44px',
    }}>
      <p style={{ fontSize: 22, fontWeight: 500, color: 'var(--color-text-primary)', textAlign: 'center', marginBottom: 24 }}>
        What&apos;s worth your attention?
      </p>

      {/* Input shell */}
      <div style={{
        width: '100%', maxWidth: 420, borderRadius: 22,
        border: '0.5px solid var(--color-border-secondary)',
        background: 'var(--color-background-primary)',
        transition: 'border-color 0.2s',
      }}
        onFocusCapture={e => { (e.currentTarget as HTMLDivElement).style.borderColor = '#0F6E56'; }}
        onBlurCapture={e => { (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--color-border-secondary)'; }}
      >
        <textarea
          ref={textareaRef}
          value={query}
          onChange={e => { setQuery(e.target.value); }}
          onKeyDown={handleKeyDown}
          placeholder="Tell me what to watch... e.g. Apple, Fed rates, EU AI regulation"
          style={{
            width: '100%', display: 'block',
            padding: '14px 18px 10px', border: 'none', outline: 'none', resize: 'none',
            fontSize: 14, color: 'var(--color-text-primary)', background: 'transparent',
            minHeight: 52, maxHeight: 100, lineHeight: 1.6,
            fontFamily: 'inherit', boxSizing: 'border-box',
          }}
          rows={1}
        />

        {/* Inner action bar */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 5,
          padding: '7px 10px', borderTop: '0.5px solid var(--color-border-tertiary)',
        }}>
          {/* Frequency pill */}
          <button
            onClick={() => togglePanel('frequency')}
            style={{ ...pillBase, ...(openPanel === 'frequency' ? pillActive : {}) }}
          >
            <Clock size={11} />
            {frequency}
            <ChevronDown size={10} />
          </button>

          {/* Coverage pill */}
          <button
            onClick={() => togglePanel('coverage')}
            style={{ ...pillBase, ...(openPanel === 'coverage' ? pillActive : {}) }}
          >
            <ScanLine size={11} />
            {coverage}
            <ChevronDown size={10} />
          </button>

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={submitting || !query.trim()}
            aria-label="Track this topic"
            style={{
              width: 30, height: 30, borderRadius: '50%',
              background: query.trim() ? 'var(--color-text-primary)' : 'var(--color-border-secondary)',
              border: 'none', cursor: query.trim() ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s', flexShrink: 0,
            }}
            onMouseEnter={e => { if (query.trim()) (e.currentTarget as HTMLButtonElement).style.background = '#0F6E56'; }}
            onMouseLeave={e => { if (query.trim()) (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-text-primary)'; }}
          >
            <ArrowUp size={13} color="var(--color-background-primary)" />
          </button>
        </div>
      </div>

      {/* Dropdown panels — rendered below shell */}
      {openPanel === 'frequency' && (
        <div style={{ width: '100%', maxWidth: 420 }}>
          <DropdownPanel
            options={FREQUENCY_OPTIONS}
            selected={frequency}
            onSelect={label => { setFrequency(label); setOpenPanel(null); }}
          />
        </div>
      )}
      {openPanel === 'coverage' && (
        <div style={{ width: '100%', maxWidth: 420 }}>
          <DropdownPanel
            options={COVERAGE_OPTIONS}
            selected={coverage}
            onSelect={label => { setCoverage(label); setOpenPanel(null); }}
          />
        </div>
      )}

      {/* Upgrade nudge */}
      {nudge && (
        <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', textAlign: 'center', marginTop: 12, maxWidth: 420 }}>
          Private topics need Pro. Follow a shared topic above (free), or{' '}
          <span style={{ color: 'var(--color-text-info)', cursor: 'pointer', textDecoration: 'underline' }}>
            upgrade
          </span>.
        </p>
      )}

      {/* Suggestion pills */}
      <div style={{
        width: '100%', maxWidth: 420, marginTop: 14,
        display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'center',
      }}>
        {SUGGESTION_PILLS.map(pill => (
          <button
            key={pill.label}
            onClick={() => fillSuggestion(pill.fill)}
            style={{
              padding: '5px 11px', borderRadius: 20, cursor: 'pointer',
              border: '0.5px solid #A3D9C5', background: '#F0FAF6',
              fontSize: 12, color: 'var(--color-text-primary)', fontFamily: 'inherit',
              transition: 'background 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => {
              const b = e.currentTarget as HTMLButtonElement;
              b.style.background = '#D7F3E9';
              b.style.borderColor = '#5DCAA5';
            }}
            onMouseLeave={e => {
              const b = e.currentTarget as HTMLButtonElement;
              b.style.background = '#F0FAF6';
              b.style.borderColor = '#A3D9C5';
            }}
          >
            {pill.label}
          </button>
        ))}
      </div>
    </div>
  );
}
