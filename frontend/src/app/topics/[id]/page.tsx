import { apiFetch } from "@/lib/api";
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { formatDistanceToNow } from 'date-fns';
import {
  ArrowLeft, Clock, Zap, BookOpen, GitBranch, BarChart2,
  ExternalLink, TrendingUp, TrendingDown, Activity
} from 'lucide-react';
import ScanButton from '@/components/topics/ScanButton';
import TopicTabs from '@/components/topics/TopicTabs';
import { EmptyState } from '@/components/ui/EmptyState';
import { FadeIn, StaggerList, StaggerItem } from '@/components/ui/motion';
import { cn } from '@/lib/utils';

// ── Types ──────────────────────────────────────────────────────────────────

interface Brief {
  id: string;
  topic_id: string;
  content: string;
  delivered_at: string;
}

interface StoryNode {
  id: string;
  summary: string;
  status: string;
  fact_count: number;
  created_at: string;
  updated_at: string;
}

interface AyrData {
  total: number;
  alphas: number;
  ayr: number;
  trusted: boolean;
  recommended_interval_s: number;
  current_interval_s: number;
  by_domain: { source_domain: string; total: number; alphas: number; ayr: number }[];
}

interface QueryVariant {
  id: string;
  query_text: string;
  scans_used: number;
  alphas_yielded: number;
  ayr: number;
  is_active: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function BriefPreview({ brief }: { brief: Brief }) {
  const preview = brief.content.replace(/[#*`_]/g, '').trim().slice(0, 200);
  const date = formatDistanceToNow(new Date(brief.delivered_at), { addSuffix: true });

  return (
    <Link
      href={`/topics/${brief.topic_id}/briefs/${brief.id}`}
      className="block group rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4 hover:border-[var(--color-brand)] hover:shadow-md transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <span className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wide">{date}</span>
        <ExternalLink className="h-3.5 w-3.5 shrink-0 text-[var(--color-text-muted)] group-hover:text-[var(--color-brand)] transition-colors" />
      </div>
      <p className="text-sm text-[var(--color-text-secondary)] line-clamp-3 leading-relaxed">{preview}…</p>
    </Link>
  );
}

function StoryCard({ story }: { story: StoryNode }) {
  const isActive = story.status === 'active';
  const updated = formatDistanceToNow(new Date(story.updated_at), { addSuffix: true });

  return (
    <div className={cn(
      'rounded-xl border p-4 transition-all',
      isActive
        ? 'border-[var(--color-brand)] bg-[var(--color-brand-subtle)]'
        : 'border-[var(--color-border)] bg-[var(--color-surface-raised)]'
    )}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold',
          isActive
            ? 'bg-[var(--color-brand)] text-white'
            : 'bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)]'
        )}>
          {isActive ? <Activity className="h-3 w-3" /> : <GitBranch className="h-3 w-3" />}
          {isActive ? 'Active' : story.status}
        </div>
        <span className="text-xs text-[var(--color-text-muted)]">{updated}</span>
      </div>
      <p className="text-sm text-[var(--color-text)] leading-relaxed mb-3">{story.summary}</p>
      <p className="text-xs text-[var(--color-text-muted)]">
        {story.fact_count ?? '?'} facts
      </p>
    </div>
  );
}

function AyrBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const color = value >= 0.5 ? 'var(--color-success)' : value >= 0.25 ? 'var(--color-warning)' : 'var(--color-danger)';
  return (
    <div className="h-1.5 w-full rounded-full bg-[var(--color-surface-overlay)] overflow-hidden">
      <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

// ── Tab Panels ─────────────────────────────────────────────────────────────

function BriefsPanel({ briefs }: { briefs: Brief[] }) {
  if (briefs.length === 0) {
    return (
      <EmptyState
        icon={BookOpen}
        title="No briefs yet"
        description="Hit 'Scan Now' to generate your first brief for this topic. It usually takes under a minute."
      />
    );
  }
  return (
    <StaggerList className="grid gap-3">
      {briefs.map((brief) => (
        <StaggerItem key={brief.id}>
          <BriefPreview brief={brief} />
        </StaggerItem>
      ))}
    </StaggerList>
  );
}

function StoriesPanel({ stories }: { stories: StoryNode[] }) {
  if (stories.length === 0) {
    return (
      <EmptyState
        icon={GitBranch}
        title="No story threads yet"
        description="Story threads appear automatically as related facts accumulate across multiple scans."
      />
    );
  }

  const active = stories.filter(s => s.status === 'active');
  const dormant = stories.filter(s => s.status !== 'active');

  return (
    <FadeIn className="space-y-6">
      {active.length > 0 && (
        <section>
          <h3 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-widest mb-3">Active threads</h3>
          <div className="grid gap-3">
            {active.map((s) => <StoryCard key={s.id} story={s} />)}
          </div>
        </section>
      )}
      {dormant.length > 0 && (
        <section>
          <h3 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-widest mb-3">Dormant threads</h3>
          <div className="grid gap-3">
            {dormant.map((s) => <StoryCard key={s.id} story={s} />)}
          </div>
        </section>
      )}
    </FadeIn>
  );
}

function InsightsPanel({ ayr, variants }: { ayr: AyrData | null; variants: QueryVariant[] }) {
  if (!ayr) {
    return (
      <EmptyState
        icon={BarChart2}
        title="Not enough data yet"
        description="Run a few scans first — insights on source quality and scan efficiency will appear here."
      />
    );
  }

  const intervalHours = Math.round(ayr.current_interval_s / 3600);
  const recommendedHours = Math.round(ayr.recommended_interval_s / 3600);

  return (
    <FadeIn className="space-y-6">
      {/* AYR summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'New info rate', value: `${Math.round(ayr.ayr * 100)}%`, sub: `${ayr.alphas} of ${ayr.total} scans yielded new facts` },
          { label: 'Scan frequency', value: `Every ${intervalHours}h`, sub: ayr.recommended_interval_s !== ayr.current_interval_s ? `optimal would be ${recommendedHours}h` : 'frequency is optimal' },
          { label: 'New facts found', value: ayr.alphas, sub: 'in the last 30 days' },
          { label: 'Data confidence', value: ayr.trusted ? 'High' : 'Building', sub: ayr.trusted ? 'Based on 10+ scans' : 'Need a few more scans' },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3">
            <p className="text-xs text-[var(--color-text-muted)] mb-1">{stat.label}</p>
            <p className="text-xl font-bold text-[var(--color-text)]">{stat.value}</p>
            <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{stat.sub}</p>
          </div>
        ))}
      </div>

      {/* By-domain table */}
      {ayr.by_domain?.length > 0 && (
        <section>
          <h3 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-widest mb-3">Source performance</h3>
          <div className="rounded-xl border border-[var(--color-border)] overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--color-surface-overlay)] text-left">
                  <th className="px-4 py-2 text-xs font-semibold text-[var(--color-text-muted)]">Source</th>
                  <th className="px-4 py-2 text-xs font-semibold text-[var(--color-text-muted)] text-right">Scans</th>
                  <th className="px-4 py-2 text-xs font-semibold text-[var(--color-text-muted)]">New info rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {ayr.by_domain.map((d) => (
                  <tr key={d.source_domain} className="bg-[var(--color-surface-raised)]">
                    <td className="px-4 py-2.5 font-medium text-[var(--color-text)]">{d.source_domain}</td>
                    <td className="px-4 py-2.5 text-right text-[var(--color-text-muted)]">{d.total}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <AyrBar value={d.ayr} />
                        <span className="text-xs text-[var(--color-text-muted)] w-8 shrink-0">{Math.round(d.ayr * 100)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Query variants */}
      {variants.length > 0 && (
        <section>
          <h3 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-widest mb-3">Search queries</h3>
          <div className="space-y-2">
            {variants.map((v) => (
              <div key={v.id} className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3">
                <div className={cn(
                  'h-2 w-2 rounded-full shrink-0',
                  v.is_active ? 'bg-[var(--color-success)]' : 'bg-[var(--color-text-muted)]'
                )} />
                <p className="text-sm text-[var(--color-text)] flex-1 truncate">{v.query_text}</p>
                <span className="text-xs text-[var(--color-text-muted)] shrink-0">{v.alphas_yielded} facts</span>
                {v.ayr > 0.5
                  ? <TrendingUp className="h-3.5 w-3.5 text-[var(--color-success)] shrink-0" />
                  : <TrendingDown className="h-3.5 w-3.5 text-[var(--color-text-muted)] shrink-0" />
                }
              </div>
            ))}
          </div>
        </section>
      )}
    </FadeIn>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default async function TopicDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const [topicRes, briefsRes, storiesRes, ayrRes, variantsRes] = await Promise.allSettled([
    apiFetch(`/topics/${id}`),
    apiFetch(`/topics/${id}/briefs`),
    apiFetch(`/topics/${id}/stories`),
    apiFetch(`/topics/${id}/ayr`),
    apiFetch(`/topics/${id}/query-variants`),
  ]);

  const topicResponse = topicRes.status === 'fulfilled' ? topicRes.value : null;
  if (!topicResponse?.ok) {
    if (topicResponse?.status === 404) notFound();
    throw new Error("Failed to load topic");
  }

  const topic = await topicResponse.json();

  const briefs: Brief[] = briefsRes.status === 'fulfilled' && briefsRes.value.ok
    ? await briefsRes.value.json() : [];
  const stories: StoryNode[] = storiesRes.status === 'fulfilled' && storiesRes.value.ok
    ? await storiesRes.value.json() : [];
  const ayr: AyrData | null = ayrRes.status === 'fulfilled' && ayrRes.value.ok
    ? await ayrRes.value.json() : null;
  const variants: QueryVariant[] = variantsRes.status === 'fulfilled' && variantsRes.value.ok
    ? await variantsRes.value.json() : [];

  const lastScan = topic.last_scan_at
    ? formatDistanceToNow(new Date(topic.last_scan_at), { addSuffix: true })
    : null;

  const tabs = [
    { id: 'briefs' as const, label: 'Briefs', count: briefs.length },
    { id: 'stories' as const, label: 'Stories', count: stories.length },
    { id: 'insights' as const, label: 'Insights' },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back link */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-brand)] transition-colors mb-6 group"
      >
        <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
        Dashboard
      </Link>

      {/* Sticky header */}
      <div className="mb-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <div className={cn(
                'h-2 w-2 rounded-full shrink-0',
                topic.is_active ? 'bg-[var(--color-success)]' : 'bg-[var(--color-text-muted)]'
              )} />
              <h1 className="text-2xl font-bold text-[var(--color-text)] truncate">{topic.raw_query}</h1>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--color-text-muted)]">
              {lastScan && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  Scanned {lastScan}
                </span>
              )}
              {ayr && (
                <span className="flex items-center gap-1">
                  <Zap className="h-3.5 w-3.5 text-[var(--color-warning)]" />
                  {Math.round(ayr.ayr * 100)}% new-info rate
                </span>
              )}
            </div>
          </div>
          <div className="shrink-0">
            <ScanButton topicId={id} />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <TopicTabs tabs={tabs} panels={{
        briefs: <BriefsPanel briefs={briefs} />,
        stories: <StoriesPanel stories={stories} />,
        insights: <InsightsPanel ayr={ayr} variants={variants} />,
      }} />
    </div>
  );
}
