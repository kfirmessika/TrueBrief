'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { Check } from 'lucide-react';

// ── Types (architecture §8 — per-user delta feed) ────────────────────────────

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
}

// Only high-signal classes get a chip; everything else stays quiet (§13 subtraction).
const CLASS_CHIP: Record<string, { label: string; color: string; bg: string }> = {
  state_change: { label: 'Milestone', color: '#1A7A52', bg: '#E6F5EE' },
  escalation:   { label: 'Escalation', color: '#B42318', bg: '#FBEAE8' },
};

// How many facts to show per topic on the home before "+N more in topic →".
const HOME_FACTS_PER_TOPIC = 4;

function FeedFactRow({ fact }: { fact: FeedFact }) {
  const chip = fact.event_class ? CLASS_CHIP[fact.event_class] : undefined;
  const domain = fact.source_domain ?? undefined;
  const favicon = domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=32` : null;
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
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
          {chip && (
            <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 7px', borderRadius: 20, background: chip.bg, color: chip.color }}>
              {chip.label}
            </span>
          )}
          {domain && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--color-text-tertiary)' }}>
              {favicon && <img src={favicon} alt={domain} width={11} height={11} style={{ borderRadius: 2 }}
                onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />}
              {domain}
            </span>
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

  // Advance last_seen so the next look shows "all caught up" (§8).
  const markAllSeen = async () => {
    try { await api.post('/feed/seen', {}); } catch { /* non-fatal */ }
    qc.invalidateQueries({ queryKey: ['feed'] });
  };

  const openTopic = (tid: string) => {
    // Mark just this topic seen (we've read it), then navigate.
    api.post('/feed/seen', { topic_ids: [tid] }).catch(() => {});
    router.push(`/topics/${tid}`);
  };

  const total = data?.total ?? 0;
  const topics = data?.topics ?? [];
  const allQuiet = !isLoading && (data?.all_quiet ?? topics.length === 0);

  return (
    <div style={{ flex: 1 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '20px 22px 14px' }}>
        <div>
          <p style={{ fontSize: 20, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
            Today
          </p>
          {!isLoading && !allQuiet && (
            <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: '3px 0 0' }}>
              <span style={{ color: 'var(--tb-green)' }}>●</span>{' '}
              {total} new across {topics.length} {topics.length === 1 ? 'topic' : 'topics'} since you looked
            </p>
          )}
        </div>
        {!isLoading && !allQuiet && (
          <button
            onClick={markAllSeen}
            title="Mark everything as seen"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 12, color: 'var(--color-text-secondary)',
              background: 'none', border: '1px solid var(--color-border-secondary)',
              borderRadius: 8, padding: '4px 10px', cursor: 'pointer',
            }}
          >
            <Check size={13} /> Mark all caught up
          </button>
        )}
      </div>

      <div style={{ padding: '0 22px 28px' }}>
        {/* Loading */}
        {isLoading && (
          <>
            {[1, 2].map(i => (
              <div key={i} style={{ border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12, padding: '16px', marginBottom: 12, background: 'var(--color-background-secondary)' }}>
                <div style={{ height: 13, width: '35%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 14 }} />
                <div style={{ height: 12, width: '92%', background: 'var(--color-background-tertiary)', borderRadius: 4, marginBottom: 7 }} />
                <div style={{ height: 12, width: '78%', background: 'var(--color-background-tertiary)', borderRadius: 4 }} />
              </div>
            ))}
          </>
        )}

        {/* All caught up — the hero state (§8/§13) */}
        {allQuiet && (
          <div style={{ textAlign: 'center', paddingTop: 96 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 44, height: 44, borderRadius: '50%', background: '#E6F5EE', marginBottom: 16,
            }}>
              <Check size={22} color="#1A7A52" />
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

        {/* The delta feed — grouped by topic, hottest first */}
        {!isLoading && !allQuiet && topics.map(topic => {
          const shown = topic.facts.slice(0, HOME_FACTS_PER_TOPIC);
          const hidden = topic.new_count - shown.length;
          return (
            <div
              key={topic.topic_id}
              style={{
                border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12,
                padding: '14px 16px 10px', marginBottom: 12,
                background: 'var(--color-background-primary)',
              }}
            >
              {/* Topic header */}
              <div
                onClick={() => openTopic(topic.topic_id)}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', marginBottom: 6 }}
              >
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  {topic.topic_name}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--tb-green)', background: 'var(--tb-green-light)', borderRadius: 20, padding: '2px 9px' }}>
                  {topic.new_count} new
                </span>
              </div>

              {/* New facts */}
              <div>
                {shown.map((f, i) => <FeedFactRow key={i} fact={f} />)}
              </div>

              {/* See more in topic */}
              <div
                onClick={() => openTopic(topic.topic_id)}
                style={{ fontSize: 12, color: 'var(--color-text-info)', cursor: 'pointer', marginTop: 6, paddingTop: 4 }}
              >
                {hidden > 0 ? `+${hidden} more · open ${topic.topic_name} →` : `Open ${topic.topic_name} →`}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
