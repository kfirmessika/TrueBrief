'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { UserStats } from '@/lib/api';

export function useStats() {
  const api = useApi();
  return useQuery({
    queryKey: ['user-stats'],
    queryFn: async () => {
      const { data } = await api.get<UserStats>('/users/me/stats');
      return data;
    },
    staleTime: 5 * 60 * 1000, // stats are coarse — 5 min cache is fine
  });
}
