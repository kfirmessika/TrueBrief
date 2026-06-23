'use client';

import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { Topic } from '@/lib/api';

/**
 * Hook to list all topics the current user is subscribed to.
 */
export function useTopics() {
  const api = useApi();
  return useQuery({
    queryKey: ['topics'],
    queryFn: async () => {
      const { data } = await api.get<Topic[]>('/topics');
      return data;
    },
  });
}

/**
 * Hook to create a new topic or subscribe to an existing one.
 */
export function useCreateTopic() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (raw_query: string) => {
      const { data } = await api.post<Topic>('/topics', { 
        raw_query, 
        poll_interval_seconds: 3600 
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topics'] });
    },
  });
}

/**
 * Hook to delete a topic.
 */
export function useDeleteTopic() {
  const api = useApi();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (topicId: string) => {
      await api.delete(`/topics/${topicId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topics'] });
    },
  });
}

/**
 * Mark all unread briefs for a topic as read.
 * Call when the user opens the topic page.
 */
export function useMarkBriefsRead() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (topicId: string) => api.post(`/topics/${topicId}/briefs/mark-read`),
    onSuccess: () => {
      // Refresh the delta feed (the V3 home) so counts update.
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });
}

/**
 * Hook to trigger a manual scan for a topic.
 */
export function useTriggerScan() {
  const api = useApi();
  return useMutation({
    mutationFn: async (topicId: string) => {
      const { data } = await api.post<{ task_id: string; topic_id: string; status: string }>(
        `/topics/${topicId}/scan`
      );
      return data;
    },
  });
}

/**
 * Hook to poll the status of a background scan task.
 */
export function useScanStatus(taskId: string | null, topicId?: string) {
  const api = useApi();
  const queryClient = useQueryClient();

  const result = useQuery({
    queryKey: ['scan-status', taskId],
    queryFn: async () => {
      const { data } = await api.get(`/scan-status/${taskId}`);
      return data;
    },
    enabled: !!taskId,
    refetchInterval: (query) => {
      const state = (query.state.data as any)?.state;
      return state === 'SUCCESS' || state === 'FAILURE' ? false : 2000;
    },
  });

  const scanState = (result.data as any)?.state;
  useEffect(() => {
    if (scanState !== 'SUCCESS' && scanState !== 'FAILURE') return;
    queryClient.invalidateQueries({ queryKey: ['topics'] });
    // Refresh the V3 home feed so a completed scan's new facts appear.
    queryClient.invalidateQueries({ queryKey: ['feed'] });
    if (topicId) {
      queryClient.invalidateQueries({ queryKey: ['topic', topicId] });
      queryClient.invalidateQueries({ queryKey: ['topic-briefs', topicId] });
      queryClient.invalidateQueries({ queryKey: ['topic-history', topicId] });
    }
  }, [scanState, topicId, queryClient]);

  return result;
}
