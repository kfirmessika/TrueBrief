'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useCallback, useContext, useEffect, useRef, use, useState, useMemo, createContext } from 'react';
import { Clock, ScanSearch } from 'lucide-react';
import { useScanStatus, useMarkBriefsRead, useTriggerScan } from '@/hooks/useTopics';

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

interface StoryNode {
  id: string;
  topic_id: string;
  title: string | null;
  summary: string;
  status: string;
  fact_count: number;
  created_at: string;
  updated_at: string;
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

// Strip the TrueBrief header line ("📋 TrueBrief | Topic | Date")
function parseContent(raw: string): string {
  const lines = raw.split('\n');
  const start = lines[0]?.includes('TrueBrief') ? 1 : 0;
  return lines.slice(start).join('\n').trim();
}

// ── Source chip data ────────────────────────────────────────────────────────

interface SourceChip {
  domain: string;
  label: string;
  url?: string; // full article URL if available
}

interface AlphaItem {
  source_domain: string;
  source_url: string | null;
  alpha_text: string;
  first_seen_at: string;
}

// Domain → alpha articles collected for this topic (page-level, read in SourcePill)
const DomainAlphasCtx = createContext<Map<string, AlphaItem[]>>(new Map());

function parseSourceLine(line: string): SourceChip[] {
  const after = line.replace(/^[→↳✓\s]*[Ss]ources?:\s*/i, '');
  // Split on ", [" boundary to handle "[Name](url), [Name](url)" format
  const parts = after.split(/,\s*(?=\[|\S)/).map(s => s.trim()).filter(Boolean);
  const chips = parts.map(part => {
    // "[Source Name](https://...)" format
    const mdLink = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
    if (mdLink) {
      const [, name, url] = mdLink;
      let domain: string;
      try { domain = new URL(url).hostname.replace(/^www\./, ''); } catch { domain = name; }
      return { domain, label: name, url };
    }
    // Legacy: plain domain name
    const domain = part.replace(/^https?:\/\/(www\.)?/, '').split('/')[0];
    return {
      domain,
      label: domain.split('.')[0].charAt(0).toUpperCase() + domain.split('.')[0].slice(1),
    };
  });
  // De-dupe by domain so a bullet citing two articles from the same outlet
  // renders ONE chip (kills the "cnn.comcnn.com" doubling). Keep the first URL.
  const seen = new Set<string>();
  return chips.filter(c => {
    if (seen.has(c.domain)) return false;
    seen.add(c.domain);
    return true;
  });
}

// ── Parse brief into sections ───────────────────────────────────────────────

interface BriefSection {
  heading: string | null;    // null = intro/badge line
  body: string;
  sources: SourceChip[];
  isBadge?: boolean;         // "6 new" / "2 updates" pill
  badgeType?: 'new' | 'update';
  badgeCount?: string;
}

function parseBriefSections(md: string): BriefSection[] {
  const lines = md.split('\n');
  const sections: BriefSection[] = [];
  let currentHeading: string | null = null;
  let currentBody: string[] = [];
  let currentSources: SourceChip[] = [];

  const flush = () => {
    const body = currentBody.join('\n').trim();
    if (body || currentSources.length) {
      sections.push({ heading: currentHeading, body, sources: currentSources });
    }
    currentHeading = null;
    currentBody = [];
    currentSources = [];
  };

  for (const line of lines) {
    const t = line.trim();

    // Skip dividers
    if (!t || /^[━─=\-]{4,}$/.test(t)) continue;

    // Badge lines: "🆕 NEW STORIES (6)" or "🔄 UPDATES (2)"
    if (/NEW STORIES|UPDATES/.test(t) && /\(\d+\)/.test(t)) {
      flush();
      const isNew = /NEW STORIES/.test(t);
      const count = t.match(/\((\d+)\)/)?.[1] ?? '';
      sections.push({
        heading: null, body: '', sources: [],
        isBadge: true,
        badgeType: isNew ? 'new' : 'update',
        badgeCount: count,
      });
      continue;
    }

    // Section heading: **Title** alone on a line
    if (/^\*\*[^*]+\*\*$/.test(t)) {
      flush();
      currentHeading = t.replace(/^\*\*|\*\*$/g, '');
      continue;
    }

    // Source line attached to current section
    if (/^[→↳✓]\s*[Ss]ource/i.test(t) || /^[Ss]ources?:/i.test(t)) {
      currentSources = parseSourceLine(t);
      continue;
    }

    // Paragraph / bullet body
    currentBody.push(line);
  }
  flush();
  return sections;
}

// ── Inline formatter ────────────────────────────────────────────────────────

function inlineFormat(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\)|`[^`]+`)/g;
  let last = 0, match, idx = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(<span key={idx++}>{text.slice(last, match.index)}</span>);
    const tok = match[0];
    if (tok.startsWith('**')) {
      parts.push(<strong key={idx++} style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith('*')) {
      parts.push(<em key={idx++}>{tok.slice(1, -1)}</em>);
    } else if (tok.startsWith('[')) {
      const linkText = tok.match(/\[([^\]]+)\]/)?.[1] ?? '';
      const href = tok.match(/\(([^)]+)\)/)?.[1] ?? '#';
      parts.push(
        <a key={idx++} href={href} target="_blank" rel="noopener noreferrer"
          style={{ color: 'inherit', textDecoration: 'underline', textDecorationColor: 'var(--color-border-secondary)', textUnderlineOffset: 2 }}>
          {linkText}
        </a>
      );
    } else if (tok.startsWith('`')) {
      parts.push(<code key={idx++} style={{ fontSize: 12, background: 'var(--color-background-tertiary)', padding: '1px 5px', borderRadius: 4, fontFamily: 'monospace' }}>{tok.slice(1, -1)}</code>);
    }
    last = match.index + tok.length;
  }
  if (last < text.length) parts.push(<span key={idx++}>{text.slice(last)}</span>);
  return <>{parts}</>;
}

function renderBodyLine(line: string, key: number): React.ReactNode {
  const t = line.trim();
  if (!t) return null;

  // Split inline " → Sources: ..." from end of line (works for bullets and paragraphs)
  const srcSplit = t.match(/^(.*?)\s+(→\s*[Ss]ources?:.+)$/);
  const mainText = srcSplit ? srcSplit[1] : t;
  const inlineSources = srcSplit ? parseSourceLine(srcSplit[2]) : [];

  // Bullet
  if (/^[\*\-•]\s+/.test(mainText)) {
    const bulletContent = mainText.replace(/^[\*\-•]\s+/, '');
    return (
      <div key={key} style={{ display: 'flex', gap: 10, margin: '2px 0' }}>
        <span style={{ color: 'var(--color-text-tertiary)', flexShrink: 0, fontSize: 16, lineHeight: '1.55' }}>·</span>
        <span style={{ fontSize: 14, color: 'var(--color-text-primary)', lineHeight: 1.6 }}>
          {inlineFormat(bulletContent)}
          {inlineSources.length > 0 && (
            <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 3, marginLeft: 5, verticalAlign: 'middle' }}>
              {inlineSources.map((chip, ci) => <SourcePill key={ci} chip={chip} />)}
            </span>
          )}
        </span>
      </div>
    );
  }

  return (
    <p key={key} style={{ fontSize: 14, color: 'var(--color-text-primary)', lineHeight: 1.65, margin: '0' }}>
      {inlineFormat(mainText)}
      {inlineSources.length > 0 && (
        <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 3, marginLeft: 5, verticalAlign: 'middle' }}>
          {inlineSources.map((chip, ci) => <SourcePill key={ci} chip={chip} />)}
        </span>
      )}
    </p>
  );
}

// ── Source chip component ───────────────────────────────────────────────────

function SourcePill({ chip }: { chip: SourceChip }) {
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${chip.domain}&sz=32`;
  const [showTooltip, setShowTooltip] = useState(false);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const domainAlphas = useContext(DomainAlphasCtx);
  const allDomainAlphas = domainAlphas.get(chip.domain) ?? [];
  // When the chip links to a specific article, show only that article's facts.
  // Fall back to all domain alphas if we can't match the URL.
  const alphas = (() => {
    if (chip.url) {
      const specific = allDomainAlphas.filter(a => a.source_url === chip.url);
      if (specific.length > 0) return specific;
    }
    return allDomainAlphas;
  })();
  const href = chip.url ?? `https://${chip.domain}`;

  const showIt = () => { if (hideTimer.current) clearTimeout(hideTimer.current); setShowTooltip(true); };
  const hideIt = () => { hideTimer.current = setTimeout(() => setShowTooltip(false), 200); };

  return (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        onMouseEnter={showIt}
        onMouseLeave={hideIt}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          fontSize: 11.5, color: 'var(--color-text-secondary)',
          background: 'var(--color-background-primary)',
          border: '1px solid var(--color-border-secondary)',
          borderRadius: 5, padding: '1px 6px 1px 4px',
          textDecoration: 'none', cursor: 'pointer',
          transition: 'border-color 0.1s',
          verticalAlign: 'middle',
        }}
      >
        <img
          src={faviconUrl}
          alt={chip.domain}
          width={12} height={12}
          style={{ borderRadius: 2, flexShrink: 0 }}
          onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
        />
        {chip.domain}
      </a>
      {showTooltip && (
        <div
          onMouseEnter={showIt}
          onMouseLeave={hideIt}
          style={{
            position: 'absolute', bottom: '100%', left: 0,
            marginBottom: 6, zIndex: 50,
            background: 'var(--color-background-primary)',
            border: '1px solid var(--color-border-secondary)',
            borderRadius: 8, padding: '10px 12px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
            pointerEvents: 'auto',
            minWidth: 280, maxWidth: 380,
            maxHeight: 340, overflowY: 'auto',
            display: 'flex', flexDirection: 'column', gap: 0,
          }}
        >
          {/* Source header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: alphas.length > 0 ? 8 : 0 }}>
            <img src={faviconUrl} alt={chip.domain} width={14} height={14} style={{ borderRadius: 3, flexShrink: 0 }} />
            <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--color-text-primary)' }}>
              {chip.domain}
            </span>
            {allDomainAlphas.length > alphas.length && (
              <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--color-text-tertiary)', flexShrink: 0 }}>
                {allDomainAlphas.length} facts from this source
              </span>
            )}
          </div>

          {/* Alpha articles */}
          {alphas.map((a, i) => (
            <div key={i} style={{
              borderTop: '0.5px solid var(--color-border-tertiary)',
              paddingTop: 8, marginTop: 2, paddingBottom: i < alphas.length - 1 ? 4 : 0,
            }}>
              <div style={{ fontSize: 11, color: 'var(--color-text-secondary)', lineHeight: 1.5, whiteSpace: 'normal' }}>
                {a.alpha_text.length > 180 ? a.alpha_text.slice(0, 177) + '…' : a.alpha_text}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 5 }}>
                <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)' }}>
                  {formatDate(a.first_seen_at)}
                </span>
                {a.source_url && (
                  <a
                    href={a.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 10, color: 'var(--tb-green)', textDecoration: 'none', flexShrink: 0 }}
                  >
                    View article →
                  </a>
                )}
              </div>
            </div>
          ))}

          {alphas.length === 0 && (
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>No articles collected yet</span>
          )}
        </div>
      )}
    </span>
  );
}

// ── Brief section renderer ──────────────────────────────────────────────────

function BriefSection({ section, idx, seen }: { section: BriefSection; idx: number; seen: boolean }) {
  if (section.isBadge) {
    // Hide the "X new / X updates" badge once the user has already seen this brief
    if (seen) return null;
    const isNew = section.badgeType === 'new';
    return (
      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 14px' }}>
        <span style={{
          fontSize: 11, fontWeight: 600, padding: '3px 9px', borderRadius: 20,
          background: isNew ? '#E6F5EE' : '#EEF3FB',
          color: isNew ? '#1A7A52' : '#2B5FA5',
          letterSpacing: '0.01em',
        }}>
          {isNew ? `${section.badgeCount} new` : `${section.badgeCount} updates`}
        </span>
        <div style={{ flex: 1, height: '0.5px', background: 'var(--color-border-tertiary)' }} />
      </div>
    );
  }

  const bodyLines = section.body.split('\n');

  return (
    <div key={idx} style={{ marginBottom: 18 }}>
      {section.heading && (
        <p style={{
          fontSize: 13, fontWeight: 650, color: 'var(--color-text-primary)',
          margin: '0 0 6px', letterSpacing: '0.01em',
        }}>
          {section.heading}
        </p>
      )}
      <div style={{ fontSize: 14, color: 'var(--color-text-primary)', lineHeight: 1.65 }}>
        {bodyLines.map((line, li) => renderBodyLine(line, li))}
        {/* Inline source chips after the paragraph */}
        {section.sources.length > 0 && (
          <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: 4, marginLeft: 5, verticalAlign: 'middle' }}>
            {section.sources.map((chip, ci) => <SourcePill key={`${chip.domain}-${ci}`} chip={chip} />)}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Brief bubble ───────────────────────────────────────────────────────────

function BriefBubble({ brief, isLast, seen }: { brief: Brief; isLast: boolean; seen: boolean }) {
  const body = parseContent(brief.content);
  const isError = body.toLowerCase().includes('error generating') || body.length < 30;

  if (isError) return null;

  const sections = parseBriefSections(body);
  // Collect all unique domains for the footer
  const allDomains = Array.from(new Set(sections.flatMap(s => s.sources.map(c => c.domain)))).slice(0, 8);

  return (
    <div style={{
      marginBottom: isLast ? 0 : 32,
      paddingBottom: isLast ? 0 : 32,
      borderBottom: isLast ? 'none' : '0.5px solid var(--color-border-tertiary)',
    }}>
      {/* Card */}
      <div style={{
        background: 'var(--color-background-primary)',
        borderRadius: 12, padding: '18px 20px 14px',
        border: '1px solid var(--color-border-tertiary)',
        boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
      }}>
        {sections.map((s, i) => <BriefSection key={i} section={s} idx={i} seen={seen} />)}
      </div>

      {/* Footer: all source favicons + timestamp */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, paddingLeft: 2 }}>
        <div style={{ display: 'flex', gap: 3 }}>
          {allDomains.map(d => (
            <img
              key={d}
              src={`https://www.google.com/s2/favicons?domain=${d}&sz=32`}
              alt={d}
              title={d}
              width={14} height={14}
              style={{ borderRadius: 3, opacity: 0.7 }}
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
            />
          ))}
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

// ── Story-native view ──────────────────────────────────────────────────────

const ACTIVE_WINDOW_HOURS = 48;

function timeAgoShort(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return `${Math.floor(diff / 60000)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function StoriesView({ topicId }: { topicId: string }) {
  const api = useApi();
  const { data: stories = [], isLoading } = useQuery<StoryNode[]>({
    queryKey: ['topic-stories', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/stories`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  if (isLoading) {
    return (
      <div style={{ padding: '24px 22px' }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ marginBottom: 12, background: 'var(--color-background-secondary)', borderRadius: 10, padding: '14px 16px', border: '1px solid var(--color-border-tertiary)' }}>
            <div style={{ height: 11, width: '40%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 10 }} />
            <div style={{ height: 12, width: '90%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 5 }} />
            <div style={{ height: 12, width: '75%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
          </div>
        ))}
      </div>
    );
  }

  if (stories.length === 0) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 80 }}>
        <p style={{ fontSize: 14, color: 'var(--color-text-tertiary)', margin: 0 }}>
          No stories yet. Run a scan to start tracking.
        </p>
      </div>
    );
  }

  const cutoff = Date.now() - ACTIVE_WINDOW_HOURS * 3600000;
  const active = stories.filter(s => new Date(s.updated_at).getTime() >= cutoff);
  const quiet = stories.filter(s => new Date(s.updated_at).getTime() < cutoff);

  const sectionLabel = (text: string) => (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      margin: '20px 0 10px',
    }}>
      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-tertiary)', whiteSpace: 'nowrap' }}>
        {text}
      </span>
      <div style={{ flex: 1, height: '0.5px', background: 'var(--color-border-tertiary)' }} />
    </div>
  );

  return (
    <div style={{ padding: '4px 22px 48px' }}>

      {/* Active stories */}
      {active.length > 0 && (
        <>
          {sectionLabel(`Moved recently · ${active.length}`)}
          {active.map(story => (
            <div key={story.id} style={{
              background: 'var(--color-background-primary)',
              border: '1px solid var(--color-border-tertiary)',
              borderRadius: 12,
              marginBottom: 12,
              overflow: 'hidden',
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              {/* Story head */}
              <div style={{
                padding: '11px 16px 9px',
                display: 'flex', alignItems: 'center', gap: 9,
                borderBottom: '0.5px solid var(--color-border-tertiary)',
                background: 'var(--color-background-secondary)',
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: 'var(--tb-green)',
                  boxShadow: '0 0 0 3px #E6F5EE',
                }} />
                <span style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.04em',
                  textTransform: 'uppercase', color: 'var(--color-text-primary)', flex: 1,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {story.title ?? 'Untitled Story'}
                </span>
                <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', flexShrink: 0 }}>
                  updated {timeAgoShort(story.updated_at)}
                </span>
              </div>

              {/* Story summary — the hidden asset made visible */}
              <div style={{ padding: '12px 16px 14px' }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.10em', textTransform: 'uppercase', color: 'var(--color-text-tertiary)', marginBottom: 6 }}>
                  Story so far
                </div>
                <p style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--color-text-primary)', margin: 0 }}>
                  {story.summary || 'No summary yet.'}
                </p>
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10, fontSize: 10, color: 'var(--color-text-tertiary)' }}>
                  <span>{story.fact_count} {story.fact_count === 1 ? 'fact' : 'facts'}</span>
                  <span>·</span>
                  <span>started {formatDate(story.created_at)}</span>
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      {/* Quiet stories */}
      {quiet.length > 0 && (
        <>
          {sectionLabel(`Quiet — no movement · ${quiet.length}`)}
          {quiet.map(story => (
            <div key={story.id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 16px',
              background: 'var(--color-background-primary)',
              border: '1px solid var(--color-border-tertiary)',
              borderRadius: 8,
              marginBottom: 5,
              cursor: 'default',
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-border-secondary)', flexShrink: 0 }} />
              <span style={{
                fontSize: 11, fontWeight: 500, textTransform: 'uppercase',
                letterSpacing: '0.03em', color: 'var(--color-text-secondary)',
                flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {story.title ?? 'Untitled Story'}
              </span>
              <span style={{ fontSize: 10, color: 'var(--color-text-tertiary)', flexShrink: 0 }}>
                {timeAgoShort(story.updated_at)}
              </span>
            </div>
          ))}
        </>
      )}

      {/* Watch footer */}
      {stories.length > 0 && (
        <div style={{
          marginTop: 20, padding: '14px 16px',
          background: 'var(--color-background-primary)',
          border: '1px dashed var(--color-border-secondary)',
          borderRadius: 10, textAlign: 'center',
          fontSize: 12, color: 'var(--color-text-tertiary)', lineHeight: 1.6,
        }}>
          <span style={{ color: 'var(--tb-green)', fontWeight: 600 }}>{active.length} of {stories.length} stories</span>
          {' '}moved in the last 48h · {quiet.length} stayed quiet
        </div>
      )}
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

function ScanProgressBar({ topicId, taskId, onDone }: { topicId: string; taskId: string; onDone: () => void }) {
  const { data: status } = useScanStatus(taskId, topicId);
  const [stepIdx, setStepIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const calledDone = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const state = status?.state ?? 'PENDING';
  const isDone = state === 'SUCCESS' || state === 'FAILURE';

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

    // Advance step label every ~4s, cap at second-to-last until done
    const stepTimer = setInterval(() => {
      setStepIdx(i => Math.min(i + 1, SCAN_STEPS.length - 2));
    }, 4000);

    // Animate progress bar: grow fast at start, slow near 90%
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
  const threadRef = useRef<HTMLDivElement>(null);

  const storyGraphPaused = process.env.NEXT_PUBLIC_V3_PAUSE_STORY_GRAPH === 'true';
  const [activeTab, setActiveTab] = useState<'briefs' | 'stories'>('briefs');
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
      onError: (err: any) => {
        const status = err?.response?.status;
        if (status === 429) {
          const detail = err?.response?.data?.detail ?? '';
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

  // Track the active scan task ID (null = no scan running)
  const [scanTaskId, setScanTaskId] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(`scan_task_${id}`);
  });

  // When scan finishes, refresh topic + briefs (stable ref so ScanProgressBar effect doesn't re-fire)
  const handleScanDone = useCallback(() => {
    setScanTaskId(null);
    qc.invalidateQueries({ queryKey: ['topic', id] });
    qc.invalidateQueries({ queryKey: ['topic-briefs', id] });
    qc.invalidateQueries({ queryKey: ['topics'] });
  }, [qc, id]);

  // Mark all unread briefs as read when the user opens the topic page
  const { mutate: markRead } = useMarkBriefsRead();
  useEffect(() => { markRead(id); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Track which brief IDs this user has already seen (persisted in localStorage)
  const [seenBriefIds, setSeenBriefIds] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') return new Set();
    try {
      const raw = localStorage.getItem(`seen_briefs_${id}`);
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch { return new Set(); }
  });

  // Poll localStorage every 500ms to catch scan tasks set by the sidebar
  useEffect(() => {
    const check = () => {
      const id_ = localStorage.getItem(`scan_task_${id}`);
      setScanTaskId(prev => prev !== id_ ? id_ : prev);
    };
    check(); // run immediately on mount
    const interval = setInterval(check, 500);
    // also catch cross-tab changes
    window.addEventListener('storage', check);
    return () => { clearInterval(interval); window.removeEventListener('storage', check); };
  }, [id]);

  const { data: topic } = useQuery<Topic>({
    queryKey: ['topic', id],
    queryFn: async () => (await api.get(`/topics/${id}`)).data,
    staleTime: 0,               // always treat as stale → re-fetch on every mount
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    refetchInterval: 60_000,    // silently keep last_scan_at up to date
  });

  const { data: briefs = [], isLoading } = useQuery<Brief[]>({
    queryKey: ['topic-briefs', id],
    queryFn: async () => {
      const res = await api.get(`/topics/${id}/briefs`);
      return [...res.data].reverse();
    },
    staleTime: 0,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    refetchInterval: scanTaskId ? 5_000 : 60_000, // fast poll when scanning, slow otherwise
  });

  // Fetch known_facts (alpha articles) for this topic — powers the source chip tooltips
  const { data: knownFacts = [] } = useQuery<AlphaItem[]>({
    queryKey: ['topic-known-facts', id],
    queryFn: async () => (await api.get(`/topics/${id}/known-facts`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  // Group alphas by source domain
  const domainAlphas = useMemo(() => {
    const map = new Map<string, AlphaItem[]>();
    for (const item of knownFacts) {
      const d = item.source_domain ?? '';
      if (!d) continue;
      if (!map.has(d)) map.set(d, []);
      map.get(d)!.push(item);
    }
    return map;
  }, [knownFacts]);

  // When briefs load, record all current brief IDs as seen
  useEffect(() => {
    if (isLoading || briefs.length === 0) return;
    setSeenBriefIds(prev => {
      const next = new Set([...prev, ...briefs.map(b => b.id)]);
      try { localStorage.setItem(`seen_briefs_${id}`, JSON.stringify([...next])); } catch { /* ignore */ }
      return next;
    });
  }, [isLoading, briefs, id]);

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

  return (
    <DomainAlphasCtx.Provider value={domainAlphas}>
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
          {scanTaskId ? (
            <ScanProgressBar topicId={id} taskId={scanTaskId} onDone={handleScanDone} />
          ) : (
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
              Last scanned {timeAgo(topic?.last_scan_at ?? null)}
            </span>
          )}
          {!scanTaskId && (
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

        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 4, marginTop: 12, borderBottom: '0.5px solid var(--color-border-tertiary)', paddingBottom: 0 }}>
          {((['briefs', ...(!storyGraphPaused ? ['stories'] : [])] as Array<'briefs' | 'stories'>)).map(tab => (
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
              {tab === 'briefs' ? 'Briefs' : 'Stories'}
            </button>
          ))}
        </div>
      </div>

      {/* Content: Briefs thread or Stories view */}
      {activeTab === 'stories' ? (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <StoriesView topicId={id} />
        </div>
      ) : (
        /* Thread */
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
                    seen={seenBriefIds.has(brief.id)}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
    </DomainAlphasCtx.Provider>
  );
}
