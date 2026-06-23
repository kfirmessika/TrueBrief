'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Zap, Bot } from 'lucide-react';
import BriefContent from '@/components/briefs/BriefContent';

// ── Types ────────────────────────────────────────────────────────────────────

interface Topic { id: string; raw_query: string; }
interface Brief { id: string; content: string; delivered_at: string; }
interface HistoryFact {
  text: string;
  context: string | null;
  event_class: string | null;
  event_date: string | null;
  source_domain: string | null;
  source_url: string | null;
  verified_count: number;
}
interface HistoryGroup { date: string; facts: HistoryFact[]; }
interface HistoryDoc { built_at?: string; fact_count?: number; timeline: HistoryGroup[]; }

const CLASS_CHIP: Record<string, { label: string; color: string; bg: string }> = {
  state_change: { label: 'Milestone', color: '#1A7A52', bg: '#E6F5EE' },
  escalation:   { label: 'Escalation', color: '#B42318', bg: '#FBEAE8' },
};

// How many of the latest facts to assemble as the "no-LLM brief".
const ASSEMBLE_LIMIT = 10;

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return `${Math.floor(diff / 60000)}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// Strip the "📋 TrueBrief | Topic | Date" header line for a clean side-by-side.
function stripBriefHeader(md: string): string {
  const lines = md.split('\n');
  return (lines[0]?.includes('TrueBrief') ? lines.slice(1) : lines).join('\n').trim();
}

function AssembledFact({ fact }: { fact: HistoryFact }) {
  const chip = fact.event_class ? CLASS_CHIP[fact.event_class] : undefined;
  const domain = fact.source_domain ?? undefined;
  return (
    <div style={{ display: 'flex', gap: 9, padding: '7px 0' }}>
      <span style={{
        marginTop: 6, width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
        background: chip ? chip.color : 'var(--color-border-secondary)',
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 13.5, lineHeight: 1.5, color: 'var(--color-text-primary)', margin: 0 }}>
          {fact.text}
        </p>
        {fact.context && (
          <p style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
            {fact.context}
          </p>
        )}
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 5 }}>
          {chip && (
            <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20, background: chip.bg, color: chip.color }}>
              {chip.label}
            </span>
          )}
          {domain && (
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{domain}</span>
          )}
          {fact.verified_count > 1 && (
            <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-tertiary)', background: 'var(--color-background-tertiary)', borderRadius: 5, padding: '1px 6px' }}>
              {fact.verified_count} sources
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function PanelHeader({ icon, title, sub, accent }: { icon: React.ReactNode; title: string; sub: string; accent: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14, paddingBottom: 12, borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 8, background: accent, color: '#fff', flexShrink: 0 }}>
        {icon}
      </span>
      <div>
        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>{title}</p>
        <p style={{ fontSize: 11, color: 'var(--color-text-tertiary)', margin: '1px 0 0' }}>{sub}</p>
      </div>
    </div>
  );
}

export default function ComparePage() {
  const api = useApi();

  const { data: topics = [] } = useQuery<Topic[]>({
    queryKey: ['topics'],
    queryFn: async () => (await api.get('/topics')).data,
    staleTime: 60_000,
  });

  const [picked, setPicked] = useState<string | null>(null);
  const topicId = picked ?? topics[0]?.id ?? null;
  const topicName = topics.find(t => t.id === topicId)?.raw_query ?? '';

  const { data: history } = useQuery<HistoryDoc>({
    queryKey: ['topic-history', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/history`)).data,
    enabled: !!topicId,
    staleTime: 60_000,
  });

  const { data: briefs = [] } = useQuery<Brief[]>({
    queryKey: ['topic-briefs', topicId],
    queryFn: async () => (await api.get(`/topics/${topicId}/briefs`)).data,
    enabled: !!topicId,
    staleTime: 60_000,
  });

  // No-LLM side: the latest facts assembled from the history timeline.
  const assembled: HistoryFact[] = (history?.timeline ?? [])
    .flatMap(g => g.facts)
    .slice(0, ASSEMBLE_LIMIT);

  // LLM side: the most recent non-empty brief.
  const latestBrief = [...briefs]
    .filter(b => b.content && b.content.length > 40 && !b.content.toLowerCase().includes('error generating'))
    .sort((a, b) => new Date(b.delivered_at).getTime() - new Date(a.delivered_at).getTime())[0];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 24px 60px' }}>
      {/* Header */}
      <Link href="/admin" style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--color-text-tertiary)', textDecoration: 'none', marginBottom: 14 }}>
        <ArrowLeft size={13} /> Admin
      </Link>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
        Compare · fact-delta vs LLM brief
      </h1>
      <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '0 0 18px', maxWidth: 680, lineHeight: 1.5 }}>
        The retire-or-keep call for the live-path briefer (architecture §15 step 4). Left is assembled
        straight from stored facts + their inline context — <strong style={{ color: 'var(--color-text-secondary)' }}>$0, no LLM</strong>.
        Right is the current Gemini-written brief. If the left reads well enough, the briefer can leave the live path.
      </p>

      {/* Topic picker */}
      <select
        value={topicId ?? ''}
        onChange={e => setPicked(e.target.value)}
        style={{
          fontSize: 13, color: 'var(--color-text-primary)',
          background: 'var(--color-background-secondary)',
          border: '0.5px solid var(--color-border-secondary)',
          borderRadius: 8, padding: '8px 12px', marginBottom: 22, minWidth: 240,
          fontFamily: 'inherit', cursor: 'pointer',
        }}
      >
        {topics.length === 0 && <option>No topics</option>}
        {topics.map(t => <option key={t.id} value={t.id}>{t.raw_query}</option>)}
      </select>

      {/* Two panels */}
      <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {/* LEFT — no-LLM assembly */}
        <div style={{ flex: '1 1 420px', minWidth: 320, background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12, padding: '18px 20px' }}>
          <PanelHeader
            icon={<Zap size={15} />}
            title="Assembled from facts"
            sub={`$0 · no LLM · ${assembled.length} latest facts`}
            accent="var(--tb-green)"
          />
          {assembled.length === 0 && (
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>No facts yet for this topic.</p>
          )}
          {assembled.map((f, i) => <AssembledFact key={i} fact={f} />)}
        </div>

        {/* RIGHT — LLM brief */}
        <div style={{ flex: '1 1 420px', minWidth: 320, background: 'var(--color-background-primary)', border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12, padding: '18px 20px' }}>
          <PanelHeader
            icon={<Bot size={15} />}
            title="LLM brief"
            sub={latestBrief ? `1 Gemini call · ${timeAgo(latestBrief.delivered_at)}` : '1 Gemini call'}
            accent="#6366f1"
          />
          {latestBrief
            ? <div style={{ fontSize: 14 }}><BriefContent content={stripBriefHeader(latestBrief.content)} /></div>
            : <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)' }}>No brief generated yet for this topic.</p>}
        </div>
      </div>
    </div>
  );
}
