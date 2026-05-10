'use client';

import { useTopics, useCreateTopic, useDeleteTopic, useTriggerScan } from '@/hooks/useTopics';
import { useTier } from '@/hooks/useTier';
import { TopicCard } from '@/components/topics/TopicCard';
import { AddTopicForm } from '@/components/topics/AddTopicForm';
import { UpgradeBanner } from '@/components/topics/UpgradeBanner';
import { Toast, useToast } from '@/components/ui/Toast';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

import { Topic, BillingStatus } from '@/lib/api';

interface DashboardClientProps {
  initialTopics: Topic[];
  initialBilling: BillingStatus | null;
}

export default function DashboardClient({ initialTopics, initialBilling }: DashboardClientProps) {
  const { data: topics, isLoading: topicsLoading } = useTopics();
  // We don't strictly NEED to pass initial data to useQuery if we pre-fetched 
  // on the server and use dehydration, but since the spec asked for props:
  const { data: billing } = useTier();
  const { toast, showToast, hideToast } = useToast();
  
  const createMutation = useCreateTopic();
  const deleteMutation = useDeleteTopic();
  const scanMutation = useTriggerScan();

  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const handleCreate = async (query: string) => {
    try {
      await createMutation.mutateAsync(query);
      showToast('Topic added successfully!', 'success');
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to add topic';
      showToast(detail, 'error');
    }
  };

  const handleDelete = async () => {
    if (!deleteTargetId) return;
    try {
      await deleteMutation.mutateAsync(deleteTargetId);
      showToast('Topic deleted', 'info');
    } catch (err: any) {
      showToast('Failed to delete topic', 'error');
    } finally {
      setDeleteTargetId(null);
    }
  };

  const handleScan = async (id: string) => {
    try {
      const res = await scanMutation.mutateAsync(id);
      return res.task_id;
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Scan failed to start';
      showToast(detail, 'error');
      throw err;
    }
  };

  if (topicsLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <Loader2 className="h-10 w-10 text-indigo-600 animate-spin" />
        <p className="text-slate-500 font-bold animate-pulse">Loading intelligence...</p>
      </div>
    );
  }

  const hasTopics = topics && topics.length > 0;
  const isAtCap = billing?.tier === 'free' && (topics?.length || 0) >= (billing?.limits?.max_topics || 2);

  return (
    <div className="space-y-10 py-10">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight">Your Topics</h1>
          <p className="text-slate-500 font-medium">Monitoring the delta in real-time.</p>
        </div>

        {billing && (
          <div className="bg-white border border-slate-100 rounded-2xl px-4 py-2 flex items-center gap-3 shadow-sm">
            <div className={`h-2.5 w-2.5 rounded-full ${billing.tier === 'free' ? 'bg-amber-400' : 'bg-green-500 animate-pulse'}`} />
            <span className="text-sm font-bold text-slate-700 uppercase tracking-wider">{billing.tier} Plan</span>
            <span className="text-slate-200">|</span>
            <span className="text-sm font-black text-indigo-600">{topics?.length || 0} / {billing.limits.max_topics} used</span>
          </div>
        )}
      </div>

      <div className="max-w-4xl">
        {isAtCap ? (
          <UpgradeBanner currentCount={topics?.length || 0} maxTopics={billing?.limits?.max_topics || 2} />
        ) : (
          <AddTopicForm onSubmit={handleCreate} isLoading={createMutation.isPending} />
        )}
      </div>

      {!hasTopics ? (
        <div className="bg-white rounded-[2rem] border-2 border-dashed border-slate-200 p-20 text-center shadow-inner">
          <div className="bg-slate-50 p-6 rounded-[1.5rem] w-fit mx-auto mb-8 shadow-sm">
            <Search className="h-10 w-10 text-slate-400" />
          </div>
          <h2 className="text-2xl font-black text-slate-900 mb-3 tracking-tight">No topics yet</h2>
          <p className="text-slate-500 max-w-sm mx-auto mb-10 text-lg font-medium">
            Start tracking a keyword or theme to see how it develops over time without the noise.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {topics.map((topic) => (
            <TopicCard 
              key={topic.id} 
              topic={topic} 
              onScan={handleScan}
              onDelete={(id) => setDeleteTargetId(id)}
            />
          ))}
        </div>
      )}

      {toast && <Toast {...toast} onClose={hideToast} />}
      
      <ConfirmDialog
        isOpen={!!deleteTargetId}
        title="Delete Topic?"
        description="This will stop monitoring this topic and remove all historical briefs. This action cannot be undone."
        confirmLabel="Delete Everything"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTargetId(null)}
      />
    </div>
  );
}
