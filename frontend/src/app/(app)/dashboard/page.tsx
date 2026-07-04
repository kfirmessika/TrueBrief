'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { useState, useEffect, useRef, useLayoutEffect, type CSSProperties } from 'react';
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
// (fetched in the background; auto-flips when ready; click flips either way). The
// summary fetch has a hard timeout so a slow/quota-limited LLM never hangs the card —
// it just stays on the alphas.
function TopicFlipCard({
  topic,
  onNavigate,
  api,
}: {
  topic: FeedTopic;
  onNavigate: () => void;
  api: AxiosInstance;
}) {
  const [flipped, setFlipped] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'failed'>('idle');
  const autoFlipped = useRef(false);

  const frontRef = useRef<HTMLDivElement>(null);
  const backRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number | undefined>(undefined);

  // Fetch the summary once per topic.
  useEffect(() => {
    const texts = topic.facts.map((f) => f.text).filter(Boolean);
    if (texts.length === 0) { setState('failed'); return; }
    if (texts.length === 1) {
      // One alpha — the summary IS the alpha; no LLM call, no auto-flip.
      setSummary(texts[0]);
      setState('done');
      return;
    }
    setState('loading');
    let cancelled = false;
    api
      .post(`/topics/${topic.topic_id}/summary`, { facts: texts.slice(0, 20) }, { timeout: 15_000 })
      .then((res) => {
        if (cancelled) return;
        const s = (res.data?.summary as string | null) ?? null;
        if (s) {
          setSummary(s);
          setState('done');
          if (!autoFlipped.current) { autoFlipped.current = true; setFlipped(true); }
        } else {
          setState('failed'); // backend returned null — stay on alphas
        }
      })
      .catch(() => { if (!cancelled) setState('failed'); });
    return () => { cancelled = true; };
  }, [topic.topic_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const canFlip = state === 'done' && !!summary;

  // Size the 3D card to whichever face is showing (variable content → no clipping).
  useLayoutEffect(() => {
    const measure = () => {
      const f = frontRef.current?.offsetHeight ?? 0;
      const b = backRef.current?.offsetHeight ?? 0;
      const next = flipped ? (b || f) : (f || b);
      if (next) setHeight(next);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [flipped, summary, state, topic.facts]);

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

  const Header = (
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
            <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> summarizing…
          </span>
        )}
        {canFlip && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10.5, color: 'var(--color-text-tertiary)' }}>
            <RefreshCw size={10} /> {flipped ? 'alphas' : 'summary'}
          </span>
        )}
        <span style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{topic.new_count} new</span>
      </div>
    </div>
  );

  const faceStyle: CSSProperties = {
    position: 'absolute', top: 0, left: 0, right: 0,
    backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
    padding: '14px 16px',
  };

  return (
    <div style={{ marginBottom: 16, perspective: 1400 }}>
      <div
        onClick={() => { if (canFlip) setFlipped((f) => !f); }}
        style={{
          position: 'relative',
          height,
          transformStyle: 'preserve-3d',
          transition: 'transform 0.55s cubic-bezier(.2,.7,.2,1), height 0.3s ease',
          transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
          cursor: canFlip ? 'pointer' : 'default',
        }}
      >
        {/* FRONT — alphas + sources */}
        <div
          ref={frontRef}
          style={{
            ...faceStyle,
            background: 'var(--color-background-primary)',
            border: '1px solid var(--color-border-tertiary)',
            borderRadius: 12,
          }}
        >
          {Header}
          <div>
            {topic.facts.map((fact, i) => <AlphaRow key={i} fact={fact} />)}
          </div>
          <div style={{ marginTop: 10 }}>{OpenTopicBtn}</div>
        </div>

        {/* BACK — summary */}
        <div
          ref={backRef}
          style={{
            ...faceStyle,
            transform: 'rotateY(180deg)',
            background: 'var(--color-background-primary)',
            border: '1px solid var(--color-border-tertiary)',
            borderRadius: 12,
          }}
        >
          {Header}
          <p style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--color-text-primary)', margin: '8px 0 0' }}>
            {summary}
          </p>
          <div style={{ marginTop: 12 }}>{OpenTopicBtn}</div>
        </div>
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

        {!isLoading && !allQuiet && topics.map((topic) => (
          <TopicFlipCard
            key={topic.topic_id}
            topic={topic}
            onNavigate={() => openTopic(topic.topic_id)}
            api={api}
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
