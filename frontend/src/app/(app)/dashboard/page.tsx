'use client';

import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { Check, Loader2, ArrowRight, Plus, AlertTriangle } from 'lucide-react';
import { SourceChip } from '@/components/SourceChip';
import { useSession } from '@/app/providers';
import { SignInPrompt } from '@/components/auth/SignInPrompt';

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

// The topic card: shows every unseen fact for this topic (topic.facts — the same
// salience-ranked, capped-at-40 list the /feed delta engine already computed, zero
// extra fetch/LLM cost), not a 4-bullet slice of the latest brief. The "N new" badge
// and the visible content are the same list now, so the count is never a promise the
// card doesn't keep. Full multi-day history still lives on the topic page.
function TopicFlipCard({
  topic,
  onNavigate,
}: {
  topic: FeedTopic;
  onNavigate: () => void;
}) {
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
        style={{
          background: 'var(--color-background-primary)',
          border: '1px solid var(--color-border-tertiary)',
          borderRadius: 12,
          padding: '14px 16px',
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
          <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{topic.new_count} new</span>
        </div>

        {/* Content — every unseen fact for this topic */}
        {topic.facts.length === 0 ? (
          <div>
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '8px 0' }}>
              No details available for this topic&apos;s update.
            </p>
            <div style={{ marginTop: 10 }}>{OpenTopicBtn}</div>
          </div>
        ) : (
          <div>
            {topic.facts.map((fact, i) => (
              <AlphaRow key={i} fact={fact} />
            ))}
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

  const { data, isLoading, isError } = useQuery<Feed>({
    queryKey: ['feed'],
    queryFn: async () => (await api.get('/feed')).data,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    enabled: !!session,
  });

  const { data: topicList = [] } = useQuery<{ id: string; is_scanning?: boolean }[]>({
    queryKey: ['topics'],
    queryFn: async () => (await api.get('/topics')).data,
    staleTime: 10_000,
    refetchInterval: 8_000,
    enabled: !!session,
  });

  const scanningCount = topicList.filter((t) => t.is_scanning).length;
  const prevScanning = useRef(0);
  useEffect(() => {
    if (prevScanning.current > 0 && scanningCount === 0) {
      qc.invalidateQueries({ queryKey: ['feed'] });
    }
    prevScanning.current = scanningCount;
  }, [scanningCount, qc]);

  const markAllSeen = useMutation({
    mutationFn: () => api.post('/feed/seen', {}),
    // Mirrors the old try/catch-and-invalidate-anyway behavior: a failed
    // "mark seen" call is non-fatal, so refetch regardless of outcome.
    onSettled: () => qc.invalidateQueries({ queryKey: ['feed'] }),
  });

  const openTopic = (tid: string) => {
    api.post('/feed/seen', { topic_ids: [tid] }).catch(() => {});
    router.push(`/topics/${tid}`);
  };

  const total = data?.total ?? 0;
  const topics = data?.topics ?? [];
  const allQuiet = !isLoading && !isError && (data?.all_quiet ?? topics.length === 0);
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
          {!isLoading && !isError && !allQuiet && (
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
              <span style={{ color: 'var(--tb-green)' }}>●</span>{' '}
              {total} new{topics.length > 1 ? ` across ${topics.length} topics` : ''} since you looked
            </p>
          )}
        </div>
        {!isLoading && !isError && !allQuiet && (
          <button
            onClick={() => markAllSeen.mutate()}
            disabled={markAllSeen.isPending}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 12, color: 'var(--color-text-secondary)',
              background: 'none', border: '1px solid var(--color-border-secondary)',
              borderRadius: 8, padding: '4px 10px', cursor: markAllSeen.isPending ? 'default' : 'pointer',
              flexShrink: 0, opacity: markAllSeen.isPending ? 0.5 : 1,
            }}
          >
            <Check size={12} /> {markAllSeen.isPending ? 'Marking…' : 'All caught up'}
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

        {isError && (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 40, height: 40, borderRadius: '50%', background: 'var(--tb-coral-bg)', marginBottom: 14,
            }}>
              <AlertTriangle size={20} color="var(--tb-coral-text)" />
            </div>
            <p style={{ fontSize: 16, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
              Couldn&apos;t load your feed.
            </p>
            <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: 0 }}>
              Something went wrong on our end — try refreshing the page.
            </p>
          </div>
        )}

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

        {!isLoading && !isError && !allQuiet && topics.map((topic) => (
          <TopicFlipCard
            key={topic.topic_id}
            topic={topic}
            onNavigate={() => openTopic(topic.topic_id)}
          />
        ))}

        {!isLoading && !isError && !allQuiet && quietCount > 0 && (
          <p style={{ fontSize: 13, color: 'var(--color-text-tertiary)', margin: '24px 0 0', paddingTop: 14, borderTop: '0.5px solid var(--color-border-tertiary)' }}>
            ── Nothing else moved across your other {quietCount} {quietCount === 1 ? 'topic' : 'topics'}.
          </p>
        )}
      </div>
    </div>
  );
}
