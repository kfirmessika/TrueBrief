'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import {
  clearPersistedCache,
  hydrateQueryClient,
  persistedCacheOwner,
  subscribePersistQueryClient,
} from '@/lib/queryCachePersist';
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

function SupabaseSessionProvider({
  children,
  onSessionChange,
}: {
  children: React.ReactNode;
  onSessionChange: (session: Session | null) => void;
}) {
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
      onSessionChange(session);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!mounted) return;
      setState({ session, user: session?.user ?? null, loading: false });
      onSessionChange(session);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [onSessionChange]);

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

  const [ownerId, setOwnerId] = useState<string | null>(null);

  /**
   * Keep the persisted cache tied to whoever is actually signed in.
   *
   * Signing out (or switching users) must wipe both the in-memory cache and
   * the localStorage snapshot — otherwise the previous user's topics keep
   * rendering in the sidebar for the next person to open the app. Defined
   * with useCallback because SupabaseSessionProvider takes it as a dep.
   */
  const handleSessionChange = useCallback((session: Session | null) => {
    const nextOwner = session?.user?.id ?? null;
    setOwnerId((prevOwner) => {
      if (prevOwner === nextOwner) return prevOwner;
      if (!nextOwner || persistedCacheOwner() !== nextOwner) {
        queryClient.clear();
        clearPersistedCache();
      }
      return nextOwner;
    });
  }, [queryClient]);

  useEffect(() => {
    return subscribePersistQueryClient(queryClient, ownerId);
  }, [queryClient, ownerId]);

  return (
    <SupabaseSessionProvider onSessionChange={handleSessionChange}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange={false}>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </ThemeProvider>
    </SupabaseSessionProvider>
  );
}
