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
 * SECURITY — this cache holds signed-in user data (`['topics']` is the
 * user's own topic list). Two rules follow, and both are load-bearing:
 *
 *  1. Never hydrate without an auth cookie present. Otherwise signing out
 *     leaves the previous user's topics rendered in the sidebar for anyone
 *     who opens the app next — which is exactly what happened before this
 *     guard existed.
 *  2. Snapshots record the owning user id. Hydrating into a session that
 *     belongs to a different user, or clearing on sign-out, must wipe it.
 *
 * The auth-cookie check is synchronous on purpose: hydration has to happen
 * in the same tick as QueryClient creation (see hydrateQueryClient docs),
 * which is before any async Supabase session lookup could resolve.
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

interface PersistedSnapshot {
  /** Supabase user id this cache belongs to. Never hydrate into a different one. */
  ownerId: string;
  entries: PersistedEntry[];
}

/**
 * Is there a Supabase auth cookie right now?
 *
 * @supabase/ssr stores the session in cookies named `sb-<projectRef>-auth-token`
 * (sometimes chunked with a `.0`/`.1` suffix). We only need presence, not the
 * value — this is a "is anyone signed in at all" gate, not authentication.
 * The real authorization boundary is the backend verifying the JWT; this just
 * stops stale cached data painting for a signed-out visitor.
 */
function hasAuthCookie(): boolean {
  if (typeof document === 'undefined') return false;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  if (!url) return false;
  try {
    const projectRef = new URL(url).hostname.split('.')[0];
    return document.cookie.split(';').some((c) => c.trim().startsWith(`sb-${projectRef}-auth-token`));
  } catch {
    return false;
  }
}

/** Drop the persisted snapshot entirely. Call on sign-out and on user switch. */
export function clearPersistedCache(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* storage unavailable — nothing to clear */
  }
}

/**
 * Rehydrate a freshly-created QueryClient from localStorage. Must be called
 * synchronously right after `new QueryClient(...)` (e.g. inside a
 * `useState(() => ...)` initializer) — calling it from a useEffect runs
 * after the first paint, which defeats the purpose (the skeleton would
 * still flash once before hydration lands).
 *
 * No-ops (and wipes the snapshot) when nobody is signed in.
 */
export function hydrateQueryClient(queryClient: QueryClient): void {
  if (typeof window === 'undefined') return;

  // Signed out: the snapshot is the previous session's data. Drop it rather
  // than painting another user's topics into a signed-out shell.
  if (!hasAuthCookie()) {
    clearPersistedCache();
    return;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    const snapshot = JSON.parse(raw) as PersistedSnapshot;
    if (!snapshot || !Array.isArray(snapshot.entries)) {
      clearPersistedCache();
      return;
    }

    const now = Date.now();
    for (const entry of snapshot.entries) {
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
    clearPersistedCache();
  }
}

/** The user id the current snapshot belongs to, if any. */
export function persistedCacheOwner(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return (JSON.parse(raw) as PersistedSnapshot)?.ownerId ?? null;
  } catch {
    return null;
  }
}

/**
 * Subscribe to the query cache and mirror successful query results to
 * localStorage, throttled to ~1 write/second. Returns an unsubscribe
 * function for cleanup (call from a useEffect).
 *
 * `ownerId` is the signed-in Supabase user id. Passing null disables
 * persistence entirely (signed out — there is nothing worth caching, and
 * writing would re-create the snapshot we just cleared).
 */
export function subscribePersistQueryClient(
  queryClient: QueryClient,
  ownerId: string | null,
): () => void {
  if (typeof window === 'undefined') return () => {};
  if (!ownerId) return () => {};

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

      const snapshot: PersistedSnapshot = { ownerId, entries };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
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
