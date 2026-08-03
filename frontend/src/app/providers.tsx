'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { useEffect, useState } from 'react';
import { hydrateQueryClient, subscribePersistQueryClient } from '@/lib/queryCachePersist';

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000,
          retry: 1,
        },
      },
    });
    // Hydrate synchronously (same tick as creation, before first paint) so
    // an Android WebView reload doesn't show an empty-cache skeleton flash.
    // See src/lib/queryCachePersist.ts for why this exists.
    hydrateQueryClient(client);
    return client;
  });

  useEffect(() => {
    return subscribePersistQueryClient(queryClient);
  }, [queryClient]);

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange={false}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
