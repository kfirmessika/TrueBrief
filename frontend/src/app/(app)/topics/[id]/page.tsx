'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useEffect, useRef, useState, use } from 'react';
import { Clock, X } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

interface Source {
  name: string;
  domain: string;
  url: string | null;
  original_sentence: string | null;
}

interface Fact {
  id: string;
  alpha_text: string;
  published_at: string;
  sources: Source[];
}

interface Topic {
  id: string;
  raw_query: string;
  frequency: string;
  last_scan_at: string | null;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function groupByDate(facts: Fact[]): Map<string, Fact[]> {
  const groups = new Map<string, Fact[]>();
  for (const fact of facts) {
    const key = formatDate(fact.published_at);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(fact);
  }
  return groups;
}

const SOURCE_COLORS: Record<string, string> = {
  'reuters.com':        '#1961A5',
  'politico.com':       '#1C3E6E',
  'euractiv.com':       '#0A7B6A',
  'ft.com':             '#BE431B',
  'arstechnica.com':    '#EA6B1F',
  'bbc.com':            '#B4071A',
  'bbc.co.uk':          '#B4071A',
  'bloomberg.com':      '#1A1A1A',
  'techcrunch.com':     '#0A84FF',
  'cnbc.com':           '#005594',
  'nytimes.com':        '#1A1A1A',
  'wsj.com':            '#0274B6',
};

function sourceColor(domain: string): string {
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (domain.includes(key)) return color;
  }
  // Generate a deterministic color from domain string
  let hash = 0;
  for (let i = 0; i < domain.length; i++) hash = domain.charCodeAt(i) + ((hash << 5) - hash);
  const colors = ['#4A6FA5', '#6B4FA5', '#A54F4F', '#4FA57A', '#A5834F'];
  return colors[Math.abs(hash) % colors.length];
}

function sourceInitials(domain: string): string {
  const clean = domain.replace(/^www\./, '').split('.')[0].toUpperCase();
  if (clean.length <= 2) return clean;
  return clean.slice(0, 2);
}

// ── Source icon with favicon + fallback ───────────────────────────────────

function SourceIcon({ source, active, onClick }: { source: Source; active: boolean; onClick: () => void }) {
  const [faviconOk, setFaviconOk] = useState(true);
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`;
  const color = sourceColor(source.domain);
  const initials = sourceInitials(source.domain);

  return (
    <div
      onClick={onClick}
      style={{
        width: 20, height: 20, borderRadius: '50%', cursor: 'pointer',
        background: faviconOk ? 'transparent' : color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden', flexShrink: 0,
        outline: active ? '2px solid var(--color-border-primary)' : 'none',
        outlineOffset: 2,
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.opacity = '0.7'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.opacity = '1'; }}
    >
      {faviconOk ? (
        <img
          src={faviconUrl}
          alt={source.domain}
          width={20} height={20}
          style={{ objectFit: 'cover', borderRadius: '50%' }}
          onError={() => setFaviconOk(false)}
        />
      ) : (
        <span style={{
          fontSize: initials.length > 2 ? 6 : initials.length > 1 ? 7 : 8,
          color: '#fff', fontWeight: 600, lineHeight: 1,
        }}>
          {initials}
        </span>
      )}
    </div>
  );
}

// ── Source expansion panel ─────────────────────────────────────────────────

function SourcePanel({ source }: { source: Source }) {
  return (
    <div style={{
      marginTop: 7, padding: '9px 12px',
      border: '0.5px solid var(--color-border-tertiary)',
      borderRadius: 8, background: 'var(--color-background-secondary)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)' }}>{source.name}</span>
        {source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: 'var(--color-text-info)', display: 'flex', alignItems: 'center', gap: 2 }}
          >
            Read original ↗
          </a>
        )}
      </div>
      {source.original_sentence && (
        <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.5, fontStyle: 'italic', margin: 0 }}>
          &ldquo;{source.original_sentence}&rdquo;
        </p>
      )}
    </div>
  );
}

// ── Fact item ─────────────────────────────────────────────────────────────

function FactItem({
  fact,
  isLast,
  onDismiss,
}: {
  fact: Fact;
  isLast: boolean;
  onDismiss: (id: string) => void;
}) {
  const [activeSource, setActiveSource] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const handleDismiss = () => {
    setDismissed(true);
    setTimeout(() => onDismiss(fact.id), 220);
  };

  const toggleSource = (i: number) => {
    setActiveSource(prev => prev === i ? null : i);
  };

  return (
    <div style={{
      padding: '10px 0',
      borderBottom: isLast ? 'none' : '0.5px solid var(--color-border-tertiary)',
      opacity: dismissed ? 0 : 1,
      transition: 'opacity 0.2s',
    }}>
      <p style={{ fontSize: 13, color: 'var(--color-text-primary)', lineHeight: 1.6, marginBottom: 7 }}>
        {fact.alpha_text}
      </p>

      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
        <div style={{ display: 'flex', gap: 4, flex: 1 }}>
          {fact.sources.map((src, i) => (
            <SourceIcon
              key={i}
              source={src}
              active={activeSource === i}
              onClick={() => toggleSource(i)}
            />
          ))}
        </div>
        <button
          onClick={handleDismiss}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--color-text-tertiary)', padding: 2, display: 'flex',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-text-primary)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-text-tertiary)'; }}
        >
          <X size={14} />
        </button>
      </div>

      {activeSource !== null && fact.sources[activeSource] && (
        <SourcePanel source={fact.sources[activeSource]} />
      )}

      <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
        {formatTime(fact.published_at)}
      </span>
    </div>
  );
}

// ── Date separator ─────────────────────────────────────────────────────────

function DateSeparator({ label, unreadCount }: { label: string; unreadCount?: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0 10px' }}>
      <div style={{ flex: 1, height: '0.5px', background: 'var(--color-border-tertiary)' }} />
      <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap' }}>{label}</span>
      {unreadCount !== undefined && unreadCount > 0 && (
        <span style={{
          fontSize: 10, padding: '1px 7px', borderRadius: 10,
          background: '#FAECE7', color: '#993C1D', fontWeight: 500, whiteSpace: 'nowrap',
        }}>
          Unread · {unreadCount} new
        </span>
      )}
      <div style={{ flex: 1, height: '0.5px', background: 'var(--color-border-tertiary)' }} />
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div style={{ padding: '0 22px 32px' }}>
      {[1, 2, 3].map(i => (
        <div key={i} style={{ padding: '10px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
          <div style={{ height: 13, width: '90%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
          <div style={{ height: 13, width: '70%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 8 }} />
          <div style={{ height: 20, width: 80, background: 'var(--color-background-tertiary)', borderRadius: 10 }} />
        </div>
      ))}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function TopicViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const api = useApi();
  const qc = useQueryClient();
  const threadRef = useRef<HTMLDivElement>(null);
  const [visibleFacts, setVisibleFacts] = useState<Set<string>>(new Set());

  const { data: topic } = useQuery<Topic>({
    queryKey: ['topic', id],
    queryFn: async () => (await api.get(`/topics/${id}`)).data,
    staleTime: 60_000,
  });

  const { data: facts = [], isLoading } = useQuery<Fact[]>({
    queryKey: ['topic-facts', id],
    queryFn: async () => (await api.get(`/topics/${id}/facts`)).data,
    staleTime: 30_000,
  });

  const dismiss = useMutation({
    mutationFn: (factId: string) => api.delete(`/facts/${factId}/dismiss`),
    onMutate: async (factId) => {
      await qc.cancelQueries({ queryKey: ['topic-facts', id] });
      const prev = qc.getQueryData<Fact[]>(['topic-facts', id]);
      qc.setQueryData<Fact[]>(['topic-facts', id], old => old?.filter(f => f.id !== factId) ?? []);
      return { prev };
    },
    onError: (_err, _factId, ctx) => {
      if (ctx?.prev) qc.setQueryData(['topic-facts', id], ctx.prev);
    },
  });

  const handleDismiss = (factId: string) => {
    setVisibleFacts(prev => { const next = new Set(prev); next.delete(factId); return next; });
    dismiss.mutate(factId);
  };

  // Initialize visible facts when loaded
  useEffect(() => {
    if (facts.length > 0) {
      setVisibleFacts(new Set(facts.map(f => f.id)));
    }
  }, [facts]);

  // Auto-scroll to bottom on load
  useEffect(() => {
    if (!isLoading && threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [isLoading]);

  const shown = facts.filter(f => visibleFacts.has(f.id));
  const dateGroups = groupByDate(shown);
  const dateKeys = Array.from(dateGroups.keys());

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Sticky header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--color-background-primary)',
        padding: '16px 22px 12px',
        borderBottom: '0.5px solid var(--color-border-tertiary)',
      }}>
        <p style={{ fontSize: 17, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 3px' }}>
          {topic?.raw_query ?? '…'}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11, color: 'var(--color-text-tertiary)' }}>
          <Clock size={11} />
          <span>Last scanned {timeAgo(topic?.last_scan_at ?? null)}</span>
          {topic?.frequency && (
            <span style={{
              fontSize: 10, border: '0.5px solid var(--color-border-secondary)',
              color: 'var(--color-text-secondary)', padding: '1px 6px', borderRadius: 10,
            }}>
              {topic.frequency}
            </span>
          )}
        </div>
      </div>

      {/* Thread */}
      <div ref={threadRef} style={{ flex: 1, overflowY: 'auto', padding: '0 22px 32px' }}>
        {isLoading && <Skeleton />}

        {!isLoading && shown.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <span style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: '#EF9F27', animation: 'tb-pulse 1.5s ease-in-out infinite',
              marginBottom: 12,
            }} />
            <p style={{ fontSize: 14, color: 'var(--color-text-tertiary)' }}>
              Your first scan is running. Check back in a few minutes.
            </p>
          </div>
        )}

        {dateKeys.map((dateKey, di) => {
          const dayFacts = dateGroups.get(dateKey)!;
          return (
            <div key={dateKey}>
              <DateSeparator label={dateKey} />
              {dayFacts.length === 0 ? (
                <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', fontStyle: 'italic', padding: '4px 0 8px' }}>
                  No new information
                </p>
              ) : (
                dayFacts.map((fact, fi) => (
                  <FactItem
                    key={fact.id}
                    fact={fact}
                    isLast={di === dateKeys.length - 1 && fi === dayFacts.length - 1}
                    onDismiss={handleDismiss}
                  />
                ))
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
