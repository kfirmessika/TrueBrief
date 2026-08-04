'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { BillingStatus } from '@/lib/api';

/**
 * Hook to get the current user's subscription tier and limits.
 * Cached for 5 minutes.
 *
 * `enabled` lets a signed-out caller (e.g. the settings page) suppress the
 * request entirely instead of firing an API call with no session.
 */
export function useTier(options?: { enabled?: boolean }) {
  const api = useApi();
  return useQuery({
    queryKey: ['billing-status'],
    queryFn: async () => {
      const { data } = await api.get<BillingStatus>('/billing/status');
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: options?.enabled ?? true,
  });
}
