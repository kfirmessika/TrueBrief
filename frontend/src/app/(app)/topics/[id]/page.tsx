'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useEffect, useRef, use } from 'react';
import { Clock } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

interface Brief {
  id: string;
  topic_id: string;
  content: string;
  delivered_at: string;
}

interface Topic {
  id: string;
  raw_query: string;
  frequency: string;
  last_scan_at: string | null;
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

// Strip the TrueBrief header line (first line like "🔎 TrueBrief | Bitcoin | May 30, 2026")
// and render the markdown body cleanly
function parseContent(raw: string): string {
  const lines = raw.split('\n');
  // Drop the first line if it looks like a header (contains "TrueBrief |")
  const start = lines[0]?.includes('TrueBrief') ? 1 : 0;
  return lines.slice(start).join('\n').trim();
}

// Extract domain names from markdown links: [text](url)
function extractDomains(content: string): string[] {
  const urlRegex = /\[.*?\]\((https?:\/\/[^)]+)\)/g;
  const domains = new Set<string>();
  let match;
  while ((match = urlRegex.exec(content)) !== null) {
    try {
      const domain = new URL(match[1]).hostname.replace(/^www\./, '');
      domains.add(domain);
    } catch { /* skip invalid URLs */ }
  }
  // Also match "Source: domain.com" patterns
  const srcRegex = /[Ss]ource[s]?:\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
  while ((match = srcRegex.exec(content)) !== null) {
    const d = match[1].toLowerCase();
    if (!d.startsWith('http')) domains.add(d);
  }
  return Array.from(domains).slice(0, 6);
}

const SOURCE_COLORS: Record<string, string> = {
  'reuters.com':     '#1961A5',
  'politico.com':    '#1C3E6E',
  'euractiv.com':    '#0A7B6A',
  'ft.com':          '#BE431B',
  'markets.ft.com':  '#BE431B',
  'arstechnica.com': '#EA6B1F',
  'bbc.com':         '#B4071A',
  'bbc.co.uk':       '#B4071A',
  'bloomberg.com':   '#1A1A1A',
  'techcrunch.com':  '#0A84FF',
  'cnbc.com':        '#005594',
  'nytimes.com':     '#1A1A1A',
  'wsj.com':         '#0274B6',
  'forbes.com':      '#CC2529',
  'wired.com':       '#1A1A1A',
  'theverge.com':    '#FF3B30',
  'axios.com':       '#FF3B30',
  'yahoo.com':       '#720E9E',
  'bitget.com':      '#00C087',
  'gizmodo.com':     '#FF6900',
};

function domainColor(d: string): string {
  for (const [k, c] of Object.entries(SOURCE_COLORS)) {
    if (d.includes(k) || k.includes(d)) return c;
  }
  let h = 0;
  for (let i = 0; i < d.length; i++) h = d.charCodeAt(i) + ((h << 5) - h);
  return ['#4A6FA5', '#6B4FA5', '#A54F4F', '#4FA57A', '#A5834F'][Math.abs(h) % 5];
}

function domainInitials(d: string): string {
  const clean = d.split('.')[0].toUpperCase();
  return clean.length <= 2 ? clean : clean.slice(0, 2);
}

// ── Source dot ─────────────────────────────────────────────────────────────

function SourceDot({ domain }: { domain: string }) {
  const bg = domainColor(domain);
  const initials = domainInitials(domain);
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

  return (
    <div
      title={domain}
      style={{
        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
        background: bg, overflow: 'hidden', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
    >
      <img
        src={faviconUrl}
        alt={domain}
        width={20} height={20}
        style={{ objectFit: 'cover', borderRadius: '50%' }}
        onError={e => {
          const img = e.currentTarget as HTMLImageElement;
          img.style.display = 'none';
          const parent = img.parentElement!;
          parent.innerHTML = `<span style="font-size:${initials.length > 1 ? 7 : 8}px;color:#fff;font-weight:600;line-height:1">${initials}</span>`;
        }}
      />
    </div>
  );
}

// ── Markdown renderer ──────────────────────────────────────────────────────
// Renders the pipeline's markdown output: bold, bullets, links, section headers

function renderMarkdown(md: string): React.ReactNode[] {
  const lines = md.split('\n');
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Skip empty-ish lines
    if (!line.trim() || line.trim() === '---' || /^[─=]{4,}/.test(line.trim())) {
      i++;
      continue;
    }

    // Section header: **Title** on its own line (not a bullet)
    if (/^\*\*[^*]+\*\*$/.test(line.trim())) {
      const text = line.trim().replace(/^\*\*|\*\*$/g, '');
      nodes.push(
        <p key={i} style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)', margin: '12px 0 4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {text}
        </p>
      );
      i++;
      continue;
    }

    // Bullet: starts with * or - or •
    if (/^[\*\-•]\s+/.test(line.trim())) {
      const text = line.trim().replace(/^[\*\-•]\s+/, '');
      nodes.push(
        <div key={i} style={{ display: 'flex', gap: 8, margin: '3px 0' }}>
          <span style={{ color: 'var(--color-text-tertiary)', flexShrink: 0, marginTop: 1 }}>·</span>
          <span style={{ fontSize: 13, color: 'var(--color-text-primary)', lineHeight: 1.6, flex: 1 }}>
            {inlineFormat(text)}
          </span>
        </div>
      );
      i++;
      continue;
    }

    // Source attribution line: "↳ Source: ..." or "↳ Sources: ..."
    if (/^[↳✓→]\s*[Ss]ource/.test(line.trim()) || /^[Ss]ource[s]?:/.test(line.trim())) {
      i++;
      continue; // source dots are shown separately below the bubble
    }

    // Section header lines like "🔔 NEW STORIES (4)" or "🔄 UPDATES (2)"
    if (/^[🔔🔄📌🚨ð]\s/.test(line) || /NEW STORIES|UPDATES|NO NEW/.test(line)) {
      const isNew = /NEW STORIES/.test(line);
      const isUpdate = /UPDATE/.test(line);
      const match = line.match(/\((\d+)\)/);
      const count = match ? match[1] : '';
      if (/NO NEW/.test(line)) {
        i++;
        continue;
      }
      nodes.push(
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '14px 0 6px' }}>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
            background: isNew ? '#E1F5EE' : isUpdate ? '#E6F1FB' : 'var(--color-background-tertiary)',
            color: isNew ? '#085041' : isUpdate ? '#185FA5' : 'var(--color-text-secondary)',
          }}>
            {isNew ? `${count} new` : isUpdate ? `${count} updates` : line.trim().replace(/^[🔔🔄📌🚨ð]\s*/, '')}
          </span>
        </div>
      );
      i++;
      continue;
    }

    // Regular paragraph
    const text = line.trim();
    if (text) {
      nodes.push(
        <p key={i} style={{ fontSize: 13, color: 'var(--color-text-primary)', lineHeight: 1.6, margin: '4px 0' }}>
          {inlineFormat(text)}
        </p>
      );
    }
    i++;
  }

  return nodes;
}

// Handle inline **bold**, *italic*, [link](url), `code`
function inlineFormat(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\)|`[^`]+`)/g;
  let last = 0;
  let match;
  let idx = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(<span key={idx++}>{text.slice(last, match.index)}</span>);
    }
    const token = match[0];
    if (token.startsWith('**')) {
      parts.push(<strong key={idx++} style={{ fontWeight: 600 }}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*')) {
      parts.push(<em key={idx++}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith('[')) {
      const linkText = token.match(/\[([^\]]+)\]/)?.[1] ?? '';
      const href = token.match(/\(([^)]+)\)/)?.[1] ?? '#';
      parts.push(
        <a key={idx++} href={href} target="_blank" rel="noopener noreferrer"
          style={{ color: 'var(--color-text-info)', textDecoration: 'none', borderBottom: '0.5px solid var(--color-text-info)' }}>
          {linkText}
        </a>
      );
    } else if (token.startsWith('`')) {
      parts.push(<code key={idx++} style={{ fontSize: 12, background: 'var(--color-background-tertiary)', padding: '1px 4px', borderRadius: 3 }}>{token.slice(1, -1)}</code>);
    }
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(<span key={idx++}>{text.slice(last)}</span>);
  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : <>{parts}</>;
}

// ── Brief bubble ───────────────────────────────────────────────────────────

function BriefBubble({ brief, isLast }: { brief: Brief; isLast: boolean }) {
  const body = parseContent(brief.content);
  const isError = body.toLowerCase().includes('error generating') || body.length < 30;
  const domains = extractDomains(brief.content);

  if (isError) return null; // skip error briefs silently

  return (
    <div style={{
      marginBottom: isLast ? 0 : 24,
      paddingBottom: isLast ? 0 : 24,
      borderBottom: isLast ? 'none' : '0.5px solid var(--color-border-tertiary)',
    }}>
      {/* Content */}
      <div style={{
        background: 'var(--color-background-secondary)',
        borderRadius: 12, padding: '14px 16px',
        borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'var(--color-border-tertiary)',
      }}>
        {renderMarkdown(body)}
      </div>

      {/* Footer: source dots + timestamp */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, paddingLeft: 2 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {domains.map(d => <SourceDot key={d} domain={d} />)}
        </div>
        <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
          {formatTime(brief.delivered_at)}
        </span>
      </div>
    </div>
  );
}

// ── Date separator ─────────────────────────────────────────────────────────

function DateSeparator({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '20px 0 16px' }}>
      <div style={{ flex: 1, height: '0.5px', background: 'var(--color-border-tertiary)' }} />
      <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap' }}>{label}</span>
      <div style={{ flex: 1, height: '0.5px', background: 'var(--color-border-tertiary)' }} />
    </div>
  );
}

// ── Skeleton ───────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div>
      {[1, 2].map(i => (
        <div key={i} style={{ marginBottom: 24 }}>
          <div style={{ background: 'var(--color-background-secondary)', borderRadius: 12, padding: '14px 16px', borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'var(--color-border-tertiary)' }}>
            <div style={{ height: 12, width: '30%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 12 }} />
            <div style={{ height: 13, width: '95%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 13, width: '85%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 13, width: '70%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 8, paddingLeft: 2 }}>
            {[1, 2, 3].map(j => <div key={j} style={{ width: 20, height: 20, borderRadius: '50%', background: 'var(--color-background-tertiary)' }} />)}
          </div>
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

  const { data: topic } = useQuery<Topic>({
    queryKey: ['topic', id],
    queryFn: async () => (await api.get(`/topics/${id}`)).data,
    staleTime: 60_000,
  });

  const { data: briefs = [], isLoading } = useQuery<Brief[]>({
    queryKey: ['topic-briefs', id],
    queryFn: async () => {
      const res = await api.get(`/topics/${id}/briefs`);
      // API returns newest first — reverse for chat order (oldest at top)
      return [...res.data].reverse();
    },
    staleTime: 30_000,
  });

  // Auto-scroll to bottom (newest brief) on load
  useEffect(() => {
    if (!isLoading && threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [isLoading, briefs]);

  // Group briefs by date
  const groups = new Map<string, Brief[]>();
  for (const b of briefs) {
    const key = formatDate(b.delivered_at);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(b);
  }

  const visibleBriefs = briefs.filter(b => {
    const body = parseContent(b.content);
    return !(body.toLowerCase().includes('error generating') || body.length < 30);
  });

  void qc; // suppress unused warning

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
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
            Last scanned {timeAgo(topic?.last_scan_at ?? null)}
          </span>
          {topic?.frequency && (
            <span style={{
              fontSize: 10, borderWidth: '0.5px', borderStyle: 'solid', borderColor: 'var(--color-border-secondary)',
              color: 'var(--color-text-secondary)', padding: '1px 6px', borderRadius: 10,
            }}>
              {topic.frequency}
            </span>
          )}
        </div>
      </div>

      {/* Thread */}
      <div ref={threadRef} style={{ flex: 1, overflowY: 'auto', padding: '0 22px 40px' }}>
        {isLoading && (
          <div style={{ paddingTop: 20 }}>
            <Skeleton />
          </div>
        )}

        {!isLoading && visibleBriefs.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <div style={{
              display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
              background: '#EF9F27', animation: 'tb-pulse 1.5s ease-in-out infinite',
              marginBottom: 14,
            }} />
            <p style={{ fontSize: 14, color: 'var(--color-text-tertiary)', margin: 0 }}>
              Your first scan is running. Check back in a few minutes.
            </p>
          </div>
        )}

        {Array.from(groups.entries()).map(([date, dayBriefs], gi) => {
          const visible = dayBriefs.filter(b => {
            const body = parseContent(b.content);
            return !(body.toLowerCase().includes('error generating') || body.length < 30);
          });
          if (visible.length === 0) return null;
          const isLastGroup = gi === groups.size - 1;
          return (
            <div key={date}>
              <DateSeparator label={date} />
              {visible.map((brief, bi) => (
                <BriefBubble
                  key={brief.id}
                  brief={brief}
                  isLast={isLastGroup && bi === visible.length - 1}
                />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
