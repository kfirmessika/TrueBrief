'use client';

/**
 * Hand-rolled React Query cache persister (localStorage).
 *
 * Why this exists: on Android, capacitor.config.ts loads the app in
 * REMOTE-URL mode — the WebView loads the hosted Next.js app over the
 * network rather than a bundled local build. WebView reloads (memory
 * pressure, network reconnect, app resume) create a brand-new QueryClient
 * in src/app/providers.tsx, wiping the in-memory cache and causing the
 * Topics tab (and anything else) to re-show its loading skeleton every
 * few minutes. gcTime and placeholderData only protect in-memory state,
 * so they don't survive a reload — this does, by mirroring successful
 * query results to localStorage and rehydrating synchronously before the
 * first paint.
 *
 * No dependency — deliberately hand-rolled instead of
 * @tanstack/react-query-persist-client to avoid adding a new package.
 */

import type { Query, QueryClient } from '@tanstack/react-query';

const STORAGE_KEY = 'tb-rq-cache-v1';
const MAX_AGE_MS = 24 * 60 * 60 * 1000; // discard entries older than 24h on hydrate
const WRITE_THROTTLE_MS = 1000;

interface PersistedEntry {
  queryKey: unknown[];
  queryHash: string;
  state: {
    data: unknown;
    dataUpdatedAt: number;
    status: string;
  };
}

/**
 * Rehydrate a freshly-created QueryClient from localStorage. Must be called
 * synchronously right after `new QueryClient(...)` (e.g. inside a
 * `useState(() => ...)` initializer) — calling it from a useEffect runs
 * after the first paint, which defeats the purpose (the skeleton would
 * still flash once before hydration lands).
 */
export function hydrateQueryClient(queryClient: QueryClient): void {
  if (typeof window === 'undefined') return;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    const entries = JSON.parse(raw) as PersistedEntry[];
    if (!Array.isArray(entries)) return;

    const now = Date.now();
    for (const entry of entries) {
      if (!entry || !Array.isArray(entry.queryKey) || !entry.state) continue;
      if (entry.state.status !== 'success') continue;
      if (now - entry.state.dataUpdatedAt > MAX_AGE_MS) continue;

      queryClient.setQueryData(entry.queryKey, entry.state.data, {
        updatedAt: entry.state.dataUpdatedAt,
      });
    }
  } catch {
    // Corrupt JSON, disabled/full localStorage, etc. — never let a bad
    // cache snapshot break the app; it just falls back to a normal load.
  }
}

/**
 * Subscribe to the query cache and mirror successful query results to
 * localStorage, throttled to ~1 write/second. Returns an unsubscribe
 * function for cleanup (call from a useEffect).
 */
export function subscribePersistQueryClient(queryClient: QueryClient): () => void {
  if (typeof window === 'undefined') return () => {};

  let timer: ReturnType<typeof setTimeout> | null = null;

  const writeSnapshot = () => {
    timer = null;
    try {
      const queries = queryClient.getQueryCache().getAll();
      const entries: PersistedEntry[] = [];

      for (const query of queries as Query[]) {
        const state = query.state;
        if (state.status !== 'success') continue;

        entries.push({
          queryKey: query.queryKey as unknown[],
          queryHash: query.queryHash,
          state: {
            data: state.data,
            dataUpdatedAt: state.dataUpdatedAt,
            status: state.status,
          },
        });
      }

      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    } catch {
      // Storage full, quota exceeded, unserializable data, etc. — skip
      // this write silently rather than throwing inside a cache subscriber.
    }
  };

  const unsubscribe = queryClient.getQueryCache().subscribe(() => {
    if (timer) return;
    timer = setTimeout(writeSnapshot, WRITE_THROTTLE_MS);
  });

  return () => {
    unsubscribe();
    if (timer) clearTimeout(timer);
  };
}
