'use client';

import { useTopics, useCreateTopic, useDeleteTopic, useTriggerScan } from '@/hooks/useTopics';
import { useTier } from '@/hooks/useTier';
import { useStats } from '@/hooks/useStats';
import { TopicCard } from '@/components/topics/TopicCard';
import { AddTopicForm } from '@/components/topics/AddTopicForm';
import { UpgradeBanner } from '@/components/topics/UpgradeBanner';
import { TimeSavedBadge } from '@/components/dashboard/TimeSavedBadge';
import { Toast, useToast } from '@/components/ui/Toast';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { StaggerList, StaggerItem, FadeIn } from '@/components/ui/motion';
import { useState } from 'react';
import { Search } from 'lucide-react';
import { Topic, BillingStatus } from '@/lib/api';
import { cn } from '@/lib/utils';

interface DashboardClientProps {
  initialTopics: Topic[];
  initialBilling: BillingStatus | null;
}

export default function DashboardClient({ initialTopics, initialBilling }: DashboardClientProps) {
  const { data: topics, isLoading: topicsLoading } = useTopics();
  const { data: billing } = useTier();
  const { data: stats } = useStats();
  const { toast, showToast, hideToast } = useToast();

  const createMutation = useCreateTopic();
  const deleteMutation = useDeleteTopic();
  const scanMutation = useTriggerScan();

  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const handleCreate = async (query: string) => {
    try {
      await createMutation.mutateAsync(query);
      showToast('Topic added!', 'success');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to add topic';
      showToast(detail, 'error');
    }
  };

  const handleDelete = async () => {
    if (!deleteTargetId) return;
    try {
      await deleteMutation.mutateAsync(deleteTargetId);
      showToast('Topic removed', 'info');
    } catch {
      showToast('Failed to delete topic', 'error');
    } finally {
      setDeleteTargetId(null);
    }
  };

  const handleScan = async (id: string) => {
    try {
      const res = await scanMutation.mutateAsync(id);
      return res.task_id;
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Scan failed to start';
      showToast(detail, 'error');
      throw err;
    }
  };

  const displayTopics = topics ?? initialTopics;
  const displayBilling = billing ?? initialBilling;
  const hasTopics = displayTopics.length > 0;
  const isAtCap = displayBilling?.tier === 'free' && displayTopics.length >= (displayBilling?.limits?.max_topics ?? 2);

  return (
    <FadeIn className="space-y-8 py-10">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h1 className="text-3xl font-bold text-[var(--color-text)] tracking-tight">Your Topics</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">Monitoring the web so you only read what's new.</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {stats && <TimeSavedBadge stats={stats} />}
          {displayBilling && (
            <div className="flex items-center gap-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3.5 py-2 shadow-sm text-sm">
              <div className={cn(
                'h-2 w-2 rounded-full',
                displayBilling.tier === 'free' ? 'bg-[var(--color-warning)]' : 'bg-[var(--color-success)] animate-pulse'
              )} />
              <span className="font-semibold text-[var(--color-text)] uppercase tracking-wide text-xs">{displayBilling.tier}</span>
              <span className="text-[var(--color-border-strong)]">·</span>
              <span className="font-bold text-[var(--color-brand)] text-xs">
                {displayTopics.length} / {displayBilling.limits.max_topics}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Add topic form */}
      <div className="max-w-2xl">
        {isAtCap ? (
          <UpgradeBanner currentCount={displayTopics.length} maxTopics={displayBilling?.limits?.max_topics ?? 2} />
        ) : (
          <AddTopicForm onSubmit={handleCreate} isLoading={createMutation.isPending} />
        )}
      </div>

      {/* Topic grid */}
      {topicsLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[0, 1, 2].map((i) => <SkeletonCard key={i} />)}
        </div>
      ) : !hasTopics ? (
        <FadeIn className="rounded-2xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-surface-raised)] py-20 px-8 text-center">
          <div className="mb-5 inline-flex rounded-2xl bg-[var(--color-surface-overlay)] p-5 border border-[var(--color-border)]">
            <Search className="h-10 w-10 text-[var(--color-text-muted)]" strokeWidth={1.25} />
          </div>
          <h2 className="text-xl font-semibold text-[var(--color-text)] mb-2">Nothing to track yet</h2>
          <p className="text-sm text-[var(--color-text-secondary)] max-w-xs mx-auto leading-relaxed mb-6">
            Enter any topic above — a company, a market, a news story — and we'll deliver only what's new each time.
          </p>
          <button
            onClick={() => document.querySelector('input')?.focus()}
            className="inline-flex items-center gap-2 bg-[var(--color-brand)] text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-colors shadow-sm"
          >
            Add your first topic
          </button>
        </FadeIn>
      ) : (
        <StaggerList className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {displayTopics.map((topic) => (
            <StaggerItem key={topic.id}>
              <TopicCard
                topic={topic}
                onScan={handleScan}
                onDelete={(id) => setDeleteTargetId(id)}
              />
            </StaggerItem>
          ))}
        </StaggerList>
      )}

      {toast && <Toast {...toast} onClose={hideToast} />}

      <ConfirmDialog
        isOpen={!!deleteTargetId}
        title="Delete Topic?"
        description="This stops monitoring and removes all historical briefs. This cannot be undone."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTargetId(null)}
      />
    </FadeIn>
  );
}
