'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { createContext, useContext, useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { hydrateQueryClient, subscribePersistQueryClient } from '@/lib/queryCachePersist';
import { createClient } from '@/lib/supabase/client';

interface SessionContextValue {
  session: Session | null;
  user: User | null;
  loading: boolean;
}

const SessionContext = createContext<SessionContextValue>({
  session: null,
  user: null,
  loading: true,
});

/** Reads the current Supabase auth session. Updates on sign-in/out/refresh. */
export function useSession(): SessionContextValue {
  return useContext(SessionContext);
}

function SupabaseSessionProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SessionContextValue>({
    session: null,
    user: null,
    loading: true,
  });

  useEffect(() => {
    const supabase = createClient();
    let mounted = true;

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!mounted) return;
      setState({ session, user: session?.user ?? null, loading: false });
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return;
      setState({ session, user: session?.user ?? null, loading: false });
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  return <SessionContext.Provider value={state}>{children}</SessionContext.Provider>;
}

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
    <SupabaseSessionProvider>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange={false}>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </ThemeProvider>
    </SupabaseSessionProvider>
  );
}
