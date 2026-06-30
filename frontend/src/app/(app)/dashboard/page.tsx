'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { Check, ChevronDown, Loader2 } from 'lucide-react';

interface FeedFact {
  text: string;
  context: string | null;
  event_class: string | null;
  event_date: string | null;
  first_seen_at: string | null;
  source_domain: string | null;
  source_url: string | null;
  verified_count: number;
}
interface FeedTopic {
  topic_id: string;
  topic_name: string;
  new_count: number;
  facts: FeedFact[];
}
interface Feed {
  all_quiet: boolean;
  total: number;
  topic_count: number;
  topics: FeedTopic[];
  date_label?: string;
}
type Envelope = 'live' | 'digest';

const CLASS_DOT: Record<string, string> = {
  state_change: '#1A7A52',
  escalation: '#B42318',
};

function timeAgo(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function FactRow({ fact, onNavigate }: { fact: FeedFact; onNavigate: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const dotColor = fact.event_class ? CLASS_DOT[fact.event_class] : undefined;
  const ago = timeAgo(fact.first_seen_at);
  const domain = fact.source_domain;
  const href = fact.source_url ?? (domain ? `https://${domain}` : undefined);
  const hasContext = !!fact.context;

  return (
    <div style={{ padding: '11px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <div
        onClick={() => hasContext ? setExpanded(e => !e) : onNavigate()}
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 8 }}
      >
        <span style={{
          marginTop: 7, width: 5, height: 5, borderRadius: '50%', flexShrink: 0,
          background: dotColor ?? 'var(--color-border-secondary)',
        }} />
        <p style={{ fontSize: 14, lineHeight: 1.55, color: 'var(--color-text-primary)', margin: 0, flex: 1 }}>
          {fact.text}
        </p>
        {hasContext && (
          <ChevronDown
            size={13}
            color="var(--color-text-tertiary)"
            style={{ flexShrink: 0, marginTop: 5, transition: 'transform 0.15s', transform: expanded ? 'rotate(180deg)' : 'none' }}
          />
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, paddingLeft: 13 }}>
        {domain && <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{domain}</span>}
        {domain && ago && <span style={{ fontSize: 12, color: 'var(--color-border-secondary)' }}>·</span>}
        {ago && <span style={{ fontSize: 12, color: 'var(--color-text-tertiary)' }}>{ago}</span>}
        {fact.verified_count > 1 && (
          <><span style={{ fontSize: 12, color: 'var(--color-border-secondary)' }}>·</span>
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{fact.verified_count} sources</span></>
        )}
      </div>
      {expanded && fact.context && (
        <div style={{ marginTop: 8, paddingLeft: 13 }}>
          <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: '0 0 6px' }}>
            {fact.context}
          </p>
          {href && (
            <a href={href} target="_blank" rel="noopener noreferrer"
              style={{ fontSize: 12, color: 'var(--tb-green)', textDecoration: 'none' }}>
              View source →
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const api = useApi();
  const router = useRouter();
  const qc = useQueryClient();
  const [envelope, setEnvelope] = useState<Envelope>('live');
  const isDigest = envelope === 'digest';

  const { data, isLoading } = useQuery<Feed>({
    queryKey: ['feed', envelope],
    queryFn: async () => (await api.get(isDigest ? '/feed/digest' : '/feed')).data,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const { data: topicList = [] } = useQuery<{ id: string; is_scanning?: boolean }[]>({
    queryKey: ['topics'],
    queryFn: async () => (await api.get('/topics')).data,
    staleTime: 10_000,
    refetchInterval: 8_000,
  });

  const scanningCount = topicList.filter(t => t.is_scanning).length;
  const prevScanning = useRef(0);
  useEffect(() => {
    if (prevScanning.current > 0 && scanningCount === 0) {
      qc.invalidateQueries({ queryKey: ['feed'] });
    }
    prevScanning.current = scanningCount;
  }, [scanningCount, qc]);

  const markAllSeen = async () => {
    try { await api.post('/feed/seen', {}); } catch { /* non-fatal */ }
    qc.invalidateQueries({ queryKey: ['feed', 'live'] });
  };

  const openTopic = (tid: string) => {
    if (!isDigest) api.post('/feed/seen', { topic_ids: [tid] }).catch(() => {});
    router.push(`/topics/${tid}`);
  };

  const total = data?.total ?? 0;
  const topics = data?.topics ?? [];
  const allQuiet = !isLoading && (data?.all_quiet ?? topics.length === 0);
  const quietCount = topicList.length - topics.length;

  return (
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 22px 12px', gap: 12 }}>
        <div>
          <p style={{ fontSize: 20, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
            {isDigest ? `Your brief · ${data?.date_label ?? 'today'}` : 'Today'}
          </p>
          {!isLoading && !allQuiet && (
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
              <span style={{ color: 'var(--tb-green)' }}>●</span>{' '}
              {total} new{topics.length > 1 ? ` across ${topics.length} topics` : ''}{' '}
              {isDigest ? 'since your last digest' : 'since you looked'}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {!isDigest && !isLoading && !allQuiet && (
            <button
              onClick={markAllSeen}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5,
                fontSize: 12, color: 'var(--color-text-secondary)',
                background: 'none', border: '1px solid var(--color-border-secondary)',
                borderRadius: 8, padding: '4px 10px', cursor: 'pointer',
              }}
            >
              <Check size={12} /> All caught up
            </button>
          )}
          <div style={{ display: 'inline-flex', background: 'var(--color-background-tertiary)', borderRadius: 8, padding: 2 }}>
            {(['live', 'digest'] as Envelope[]).map(env => (
              <button key={env} onClick={() => setEnvelope(env)} style={{
                fontSize: 11, fontWeight: envelope === env ? 600 : 400,
                color: envelope === env ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                background: envelope === env ? 'var(--color-background-primary)' : 'transparent',
                border: 'none', borderRadius: 6, padding: '3px 10px', cursor: 'pointer',
                boxShadow: envelope === env ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
              }}>
                {env === 'live' ? 'Today' : 'Digest'}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ padding: '0 22px 40px' }}>
        {scanningCount > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: 'var(--tb-amber-light, #FBF1E6)', border: '0.5px solid #F3D9B8',
            borderRadius: 10, padding: '9px 13px', marginBottom: 16,
          }}>
            <Loader2 size={13} color="#B45309" style={{ animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: 12.5, color: '#92400E' }}>
              Scanning {scanningCount} {scanningCount === 1 ? 'topic' : 'topics'}…
            </span>
          </div>
        )}

        {isLoading && [1, 2, 3].map(i => (
          <div key={i} style={{ padding: '10px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
            <div style={{ height: 14, width: `${65 + i * 7}%`, background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 6 }} />
            <div style={{ height: 11, width: '22%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
          </div>
        ))}

        {allQuiet && (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 40, height: 40, borderRadius: '50%', background: '#E6F5EE', marginBottom: 14,
            }}>
              <Check size={20} color="#1A7A52" />
            </div>
            <p style={{ fontSize: 16, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
              You&apos;re all caught up.
            </p>
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: 0 }}>
              {data && data.topic_count > 0
                ? isDigest ? 'Nothing new since your last digest.'
                  : `Nothing new across your ${data.topic_count} ${data.topic_count === 1 ? 'topic' : 'topics'}.`
                : 'Add a topic to start tracking.'}
            </p>
          </div>
        )}

        {!isLoading && !allQuiet && topics.map((topic, ti) => (
          <div key={topic.topic_id} style={{ marginBottom: ti < topics.length - 1 ? 28 : 0 }}>
            <div
              onClick={() => openTopic(topic.topic_id)}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 0, cursor: 'pointer', paddingBottom: 4 }}
            >
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {topic.topic_name}
              </span>
              <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
                {topic.new_count} new →
              </span>
            </div>
            {topic.facts.map((fact, fi) => (
              <FactRow key={fi} fact={fact} onNavigate={() => openTopic(topic.topic_id)} />
            ))}
          </div>
        ))}

        {!isLoading && !allQuiet && quietCount > 0 && (
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '24px 0 0', paddingTop: 14, borderTop: '0.5px solid var(--color-border-tertiary)' }}>
            ── Nothing else moved across your other {quietCount} {quietCount === 1 ? 'topic' : 'topics'}.
          </p>
        )}

        {isDigest && !isLoading && !allQuiet && (
          <p style={{ textAlign: 'center', fontSize: 13, color: 'var(--color-text-tertiary)', margin: '24px 0 4px' }}>
            That&apos;s everything. See you tomorrow.
          </p>
        )}
      </div>
    </div>
  );
}
