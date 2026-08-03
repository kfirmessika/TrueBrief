import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

/**
 * Supabase client for use in Server Components, Server Functions, and Route
 * Handlers. Always create a new client per request — never share/cache this
 * across requests.
 *
 * `setAll` can throw when called from a Server Component (which can't set
 * cookies) — that's fine as long as `proxy.ts` is refreshing the session on
 * every request, per Supabase's SSR guidance.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // Called from a Server Component — ignored; proxy.ts refreshes
            // the session on every request so this is not a correctness gap.
          }
        },
      },
    }
  );
}
