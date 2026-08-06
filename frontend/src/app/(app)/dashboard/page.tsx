'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { useState, useEffect, useRef, useMemo } from 'react';
import { Check, Loader2, ArrowRight, RefreshCw, Plus } from 'lucide-react';
import { SourceChip } from '@/components/SourceChip';
import { parseBrief } from '@/app/(app)/topics/[id]/page';
import { useSession } from '@/app/providers';
import { SignInPrompt } from '@/components/auth/SignInPrompt';

interface BriefRow { id: string; content: string; delivered_at: string }

// GET /public-topics — no auth required, admin-curated public topics only.
interface PublicTopic { id: string; name: string; subscriber_count: number }

/**
 * Signed-out entry-page browsing surface. "Adding" a public topic here is purely
 * client-side/ephemeral (local component state, never localStorage or the query
 * cache) — closing the tab loses the selection, same as any unauthenticated
 * ChatGPT-style session. This is intentional: it's the "sign in to keep this"
 * hook, not a real subscribe action (which requires an account server-side).
 */
function PublicTopicBrowser() {
  const api = useApi();
  const [added, setAdded] = useState<Set<string>>(new Set());

  const { data: topics = [], isLoading } = useQuery<PublicTopic[]>({
    queryKey: ['public-topics'],
    queryFn: async () => (await api.get('/public-topics')).data,
    staleTime: 60_000,
  });

  const toggle = (id: string) => {
    setAdded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  if (isLoading) {
    return (
      <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', textAlign: 'center', padding: '8px 0' }}>
        Loading public topics…
      </p>
    );
  }

  if (topics.length === 0) {
    return (
      <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', textAlign: 'center', padding: '8px 0' }}>
        No public topics available yet.
      </p>
    );
  }

  return (
    <div style={{ maxWidth: 480, margin: '0 auto' }}>
      {topics.map(t => {
        const isAdded = added.has(t.id);
        return (
          <div
            key={t.id}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
              padding: '10px 14px', border: '0.5px solid var(--color-border-tertiary)',
              borderRadius: 10, marginBottom: 8, background: 'var(--color-background-primary)',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 13.5, color: 'var(--color-text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {t.name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>
                {t.subscriber_count} following
              </div>
            </div>
            <button
              onClick={() => toggle(t.id)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 5, flexShrink: 0,
                fontSize: 12, fontWeight: 500, padding: '5px 12px', borderRadius: 8, cursor: 'pointer',
                border: isAdded ? '0.5px solid var(--tb-green-border)' : '0.5px solid var(--color-border-secondary)',
                background: isAdded ? 'var(--tb-green-light)' : 'transparent',
                color: isAdded ? 'var(--tb-green-dark)' : 'var(--color-text-secondary)',
                fontFamily: 'inherit',
              }}
            >
              {isAdded ? <><Check size={12} /> Added</> : <><Plus size={12} /> Add</>}
            </button>
          </div>
        );
      })}
      {added.size > 0 && (
        <p style={{ fontSize: 11, color: 'var(--color-text-tertiary)', textAlign: 'center', margin: '4px 0 0' }}>
          This selection is temporary — sign in to actually track a topic and get scans + briefs.
        </p>
      )}
    </div>
  );
}

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

// The flip card. Front = unseen alphas + sources (instant). Back = the lede + top
// bullets of the topic's latest STORED brief (Briefer already ran this scan — zero
// extra LLM cost, and it's the same well-synthesized output the benchmark scored
// well, not a cheap re-summary of the same facts on a worse model).
//
// Uses scaleX squeeze animation instead of 3D rotateY because the ancestor layout
// container has overflow:auto, which the CSS spec requires to flatten preserve-3d.
// The squeeze (scaleX 1→0→1) is visually equivalent and works through any overflow.
function TopicFlipCard({
  topic,
  onNavigate,
  lastRun,
}: {
  topic: FeedTopic;
  onNavigate: () => void;
  lastRun?: string | null;
}) {
  const api = useApi();
  const [showBack, setShowBack] = useState(false);
  // 'out': squeezing to invisible; 'in': expanding back; 'idle': at rest
  const [phase, setPhase] = useState<'idle' | 'out' | 'in'>('idle');
  const nextFace = useRef(false);       // which face to show after the squeeze
  const autoFlipped = useRef(false);    // guard: fire auto-flip only once

  const { data: briefs, isLoading: briefLoading, isError: briefFailed, refetch } = useQuery<BriefRow[]>({
    queryKey: ['topic-briefs', topic.topic_id, lastRun],
    queryFn: async () => (await api.get(`/topics/${topic.topic_id}/briefs`)).data,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const latest = briefs?.[0];
  const blocks = useMemo(() => (latest ? parseBrief(latest.content) : []), [latest]);
  const lede = blocks.find((b) => b.kind === 'lede');
  const bullets = blocks.filter((b) => b.kind === 'bullet').slice(0, 4);

  const state: 'loading' | 'done' | 'failed' =
    briefLoading ? 'loading' : (briefFailed || blocks.length === 0) ? 'failed' : 'done';

  // Auto-flip to the brief once it's loaded (skip the single-fact shortcut card —
  // the front face already IS the whole story at 1 fact).
  useEffect(() => {
    if (state === 'done' && topic.facts.length >= 2 && !autoFlipped.current) {
      autoFlipped.current = true;
      nextFace.current = true;
      setPhase('out');
    }
  }, [state, topic.facts.length]);

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
    if (state !== 'done' || phase !== 'idle') return;
    nextFace.current = !showBack;
    setPhase('out');
  };

  const isFlipReady = state === 'done';

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
                <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> loading brief…
              </span>
            )}
            {state === 'failed' && topic.facts.length >= 2 && (
              <button
                onClick={(e) => { e.stopPropagation(); refetch(); }}
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
                <RefreshCw size={10} /> {showBack ? 'alphas' : 'brief'}
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
            {lede && 'text' in lede && (
              <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--color-text-primary)', margin: '8px 0 8px', fontWeight: 500 }}>
                {lede.text}
              </p>
            )}
            {bullets.map((b, i) => {
              if (b.kind !== 'bullet') return null;
              return (
                <div key={i} style={{ display: 'flex', gap: 6, margin: '0 0 6px' }}>
                  <span style={{ color: 'var(--color-text-tertiary)', flexShrink: 0 }}>•</span>
                  <span style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--color-text-secondary)' }}>
                    {b.bullet.text}
                  </span>
                </div>
              );
            })}
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
  const { session } = useSession();

  const { data, isLoading } = useQuery<Feed>({
    queryKey: ['feed'],
    queryFn: async () => (await api.get('/feed')).data,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    enabled: !!session,
  });

  const { data: topicList = [] } = useQuery<{ id: string; is_scanning?: boolean; last_scan_at?: string | null }[]>({
    queryKey: ['topics'],
    queryFn: async () => (await api.get('/topics')).data,
    staleTime: 10_000,
    refetchInterval: 8_000,
    enabled: !!session,
  });

  // topicList polls every 8s; map id -> last_scan_at so each card's brief query is keyed
  // on it and picks up server-side scheduled scans (same fix as the topic page).
  const lastRunById = useMemo(
    () => Object.fromEntries(topicList.map((t) => [t.id, t.last_scan_at ?? null])),
    [topicList],
  );

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

  if (!session) {
    return (
      <div style={{ flex: 1 }}>
        <div style={{ padding: '20px 22px 4px' }}>
          <p style={{ fontSize: 20, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
            Today
          </p>
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '4px 0 0' }}>
            Browse what TrueBrief tracks publicly — sign in to track your own topics privately.
          </p>
        </div>
        <div style={{ padding: '16px 22px 0' }}>
          <PublicTopicBrowser />
        </div>
        <SignInPrompt message="Sign in to see what's new across your own tracked topics." />
      </div>
    );
  }

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

        {!isLoading && !allQuiet && topics.map((topic) => (
          <TopicFlipCard
            key={topic.topic_id}
            topic={topic}
            onNavigate={() => openTopic(topic.topic_id)}
            lastRun={lastRunById[topic.topic_id]}
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
