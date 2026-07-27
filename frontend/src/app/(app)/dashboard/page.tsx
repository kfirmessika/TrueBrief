'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { Check, Loader2, ArrowRight, RefreshCw } from 'lucide-react';
import type { AxiosInstance } from 'axios';
import { SourceChip } from '@/components/SourceChip';

interface FeedFact {
  text: string;
  context: string | null;
  event_class: string | null;
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
}

// A single unseen alpha on the front of the card: text + its source chip.
function AlphaRow({ fact }: { fact: FeedFact }) {
  return (
    <div style={{ padding: '9px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <p style={{ fontSize: 13.5, lineHeight: 1.5, color: 'var(--color-text-primary)', margin: 0 }}>
        {fact.text}
      </p>
      {fact.context && (
        <p style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
          {fact.context}
        </p>
      )}
      {(fact.source_domain || fact.source_url || fact.verified_count > 1) && (
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
          {(fact.source_domain || fact.source_url) && (
            <SourceChip domain={fact.source_domain} url={fact.source_url} />
          )}
          {fact.verified_count > 1 && (
            <span
              title={`${fact.verified_count} independent sources`}
              style={{
                fontSize: 10.5, fontWeight: 600, color: 'var(--color-text-tertiary)',
                background: 'var(--color-background-tertiary)', borderRadius: 5, padding: '1px 6px',
              }}
            >
              +{fact.verified_count - 1} more
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// The flip card. Front = unseen alphas + sources (instant). Back = cheap-LLM summary
// (fetched in the background; auto-flips when ready; click flips either way).
//
// Uses scaleX squeeze animation instead of 3D rotateY because the ancestor layout
// container has overflow:auto, which the CSS spec requires to flatten preserve-3d.
// The squeeze (scaleX 1→0→1) is visually equivalent and works through any overflow.
function TopicFlipCard({
  topic,
  onNavigate,
  api,
  delay = 0,
}: {
  topic: FeedTopic;
  onNavigate: () => void;
  api: AxiosInstance;
  delay?: number;
}) {
  const [summary, setSummary] = useState<string | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'failed'>('idle');
  const [showBack, setShowBack] = useState(false);
  // 'out': squeezing to invisible; 'in': expanding back; 'idle': at rest
  const [phase, setPhase] = useState<'idle' | 'out' | 'in'>('idle');
  const nextFace = useRef(false);       // which face to show after the squeeze
  const autoFlipped = useRef(false);    // guard: fire auto-flip only once
  const shouldAutoFlip = useRef(false); // only true for 2+ fact cards (not single-fact shortcut)

  const fetchSummary = useRef<() => void>(() => {});

  // Fetch the summary once per topic (or on retry).
  useEffect(() => {
    const texts = topic.facts.map((f) => f.text).filter(Boolean);
    if (texts.length === 0) { setState('failed'); return; }
    if (texts.length === 1) {
      // One alpha — summary IS the alpha; no LLM call, no auto-flip.
      setSummary(texts[0]);
      setState('done');
      return;
    }

    let cancelled = false;

    const doFetch = () => {
      setState('loading');
      shouldAutoFlip.current = true;
      api
        .post(`/topics/${topic.topic_id}/summary`, { facts: texts.slice(0, 40) }, { timeout: 25_000 })
        .then((res) => {
          if (cancelled) return;
          const s = (res.data?.summary as string | null) ?? null;
          if (s) { setSummary(s); setState('done'); }
          else setState('failed');
        })
        .catch(() => { if (!cancelled) setState('failed'); });
    };

    // Expose retry without dismounting the effect.
    fetchSummary.current = doFetch;

    // Stagger concurrent card requests to avoid hitting Groq rate limits.
    setState('loading');
    const timer = setTimeout(doFetch, delay);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [topic.topic_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-flip to the summary once it arrives (2+ fact cards only).
  useEffect(() => {
    if (state === 'done' && summary && shouldAutoFlip.current && !autoFlipped.current) {
      autoFlipped.current = true;
      nextFace.current = true;
      setPhase('out');
    }
  }, [state, summary]);

  // Orchestrate the squeeze: out → swap content at invisible midpoint → in.
  const handleTransitionEnd = (e: React.TransitionEvent<HTMLDivElement>) => {
    if (e.propertyName !== 'transform') return;
    if (phase === 'out') {
      setShowBack(nextFace.current); // content swaps while invisible
      setPhase('in');
    } else if (phase === 'in') {
      setPhase('idle');
    }
  };

  const flip = () => {
    if (state !== 'done' || !summary || phase !== 'idle') return;
    nextFace.current = !showBack;
    setPhase('out');
  };

  const isFlipReady = state === 'done' && !!summary;

  const OpenTopicBtn = (
    <button
      onClick={(e) => { e.stopPropagation(); onNavigate(); }}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        fontSize: 12, color: 'var(--tb-green)',
        background: 'none', border: 'none', cursor: 'pointer', padding: 0,
      }}
    >
      Open topic <ArrowRight size={12} />
    </button>
  );

  return (
    <div style={{ marginBottom: 16 }}>
      <div
        onClick={flip}
        onTransitionEnd={handleTransitionEnd}
        style={{
          background: 'var(--color-background-primary)',
          border: `1px solid ${showBack ? 'var(--tb-green, #1A7A52)' : 'var(--color-border-tertiary)'}`,
          borderRadius: 12,
          padding: '14px 16px',
          cursor: isFlipReady && phase === 'idle' ? 'pointer' : 'default',
          transform: phase === 'out' ? 'scaleX(0)' : 'scaleX(1)',
          transformOrigin: 'center',
          transition: phase === 'idle' ? 'none' : 'transform 0.15s ease-in-out',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          paddingBottom: 8, marginBottom: 2, borderBottom: '0.5px solid var(--color-border-tertiary)',
        }}>
          <span style={{
            fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.08em',
          }}>
            {topic.topic_name}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {state === 'loading' && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10.5, color: 'var(--color-text-tertiary)' }}>
                <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> summarising…
              </span>
            )}
            {state === 'failed' && topic.facts.length >= 2 && (
              <button
                onClick={(e) => { e.stopPropagation(); fetchSummary.current(); }}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 3,
                  fontSize: 10.5, color: 'var(--color-text-tertiary)',
                  background: 'none', border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 5, padding: '1px 6px', cursor: 'pointer',
                }}
              >
                <RefreshCw size={10} /> retry
              </button>
            )}
            {isFlipReady && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10.5, color: 'var(--color-text-tertiary)' }}>
                <RefreshCw size={10} /> {showBack ? 'alphas' : 'summary'}
              </span>
            )}
            <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{topic.new_count} new</span>
          </div>
        </div>

        {/* Content — swapped at the invisible midpoint of the squeeze animation */}
        {!showBack ? (
          <div>
            {topic.facts.slice(0, 8).map((fact, i) => <AlphaRow key={i} fact={fact} />)}
            {topic.facts.length > 8 && (
              <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '6px 0 0' }}>
                +{topic.facts.length - 8} more in this topic
              </p>
            )}
            <div style={{ marginTop: 10 }}>{OpenTopicBtn}</div>
          </div>
        ) : (
          <div>
            {/* pre-line: the digest form of the summary separates developments with \n bullets */}
            <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--color-text-primary)', margin: '8px 0 0', whiteSpace: 'pre-line' }}>
              {summary}
            </p>
            <div style={{ marginTop: 12 }}>{OpenTopicBtn}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const api = useApi();
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<Feed>({
    queryKey: ['feed'],
    queryFn: async () => (await api.get('/feed')).data,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  const { data: topicList = [] } = useQuery<{ id: string; is_scanning?: boolean }[]>({
    queryKey: ['topics'],
    queryFn: async () => (await api.get('/topics')).data,
    staleTime: 10_000,
    refetchInterval: 8_000,
  });

  const scanningCount = topicList.filter((t) => t.is_scanning).length;
  const prevScanning = useRef(0);
  useEffect(() => {
    if (prevScanning.current > 0 && scanningCount === 0) {
      qc.invalidateQueries({ queryKey: ['feed'] });
    }
    prevScanning.current = scanningCount;
  }, [scanningCount, qc]);

  const markAllSeen = async () => {
    try { await api.post('/feed/seen', {}); } catch { /* non-fatal */ }
    qc.invalidateQueries({ queryKey: ['feed'] });
  };

  const openTopic = (tid: string) => {
    api.post('/feed/seen', { topic_ids: [tid] }).catch(() => {});
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
            Today
          </p>
          {!isLoading && !allQuiet && (
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
              <span style={{ color: 'var(--tb-green)' }}>●</span>{' '}
              {total} new{topics.length > 1 ? ` across ${topics.length} topics` : ''} since you looked
            </p>
          )}
        </div>
        {!isLoading && !allQuiet && (
          <button
            onClick={markAllSeen}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 12, color: 'var(--color-text-secondary)',
              background: 'none', border: '1px solid var(--color-border-secondary)',
              borderRadius: 8, padding: '4px 10px', cursor: 'pointer', flexShrink: 0,
            }}
          >
            <Check size={12} /> All caught up
          </button>
        )}
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

        {isLoading && [1, 2, 3].map((i) => (
          <div key={i} style={{ padding: '14px 16px', border: '1px solid var(--color-border-tertiary)', borderRadius: 12, marginBottom: 16 }}>
            <div style={{ height: 12, width: '40%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 12 }} />
            <div style={{ height: 13, width: `${75 + i * 5}%`, background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 7 }} />
            <div style={{ height: 13, width: '55%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
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
                ? `Nothing new across your ${data.topic_count} ${data.topic_count === 1 ? 'topic' : 'topics'}.`
                : 'Add a topic to start tracking.'}
            </p>
          </div>
        )}

        {!isLoading && !allQuiet && topics.map((topic, i) => (
          <TopicFlipCard
            key={topic.topic_id}
            topic={topic}
            onNavigate={() => openTopic(topic.topic_id)}
            api={api}
            delay={i * 1000}
          />
        ))}

        {!isLoading && !allQuiet && quietCount > 0 && (
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '24px 0 0', paddingTop: 14, borderTop: '0.5px solid var(--color-border-tertiary)' }}>
            ── Nothing else moved across your other {quietCount} {quietCount === 1 ? 'topic' : 'topics'}.
          </p>
        )}
      </div>
    </div>
  );
}
