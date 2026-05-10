'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { BillingStatus } from '@/lib/api';

/**
 * Hook to get the current user's subscription tier and limits.
 * Cached for 5 minutes.
 */
export function useTier() {
  const api = useApi();
  return useQuery({
    queryKey: ['billing-status'],
    queryFn: async () => {
      const { data } = await api.get<BillingStatus>('/billing/status');
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
