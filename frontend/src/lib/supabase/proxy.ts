import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

/**
 * Refreshes the Supabase session cookie on every request. Called from
 * `src/proxy.ts` (Next.js 16 renamed `middleware.ts` -> `proxy.ts`).
 *
 * Does NOT redirect unauthenticated visitors — TrueBrief behaves like
 * ChatGPT: every route (including /dashboard, /topics, /settings) renders
 * the same app shell for signed-out visitors, and each page component
 * decides what to show based on `useSession()` (empty-state + sign-in
 * prompt instead of real data/queries). See `(app)/dashboard/page.tsx` etc.
 *
 * Do not run code between `createServerClient` and `getClaims()` — a simple
 * mistake here makes it very hard to debug users being randomly logged out
 * (per Supabase's own SSR guide).
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
          Object.entries(headers).forEach(([key, value]) =>
            supabaseResponse.headers.set(key, value)
          );
        },
      },
    }
  );

  // getClaims() validates the JWT signature against the project's published
  // public keys every time — unlike getSession(), it's safe to trust in
  // server-side code such as proxy.ts. Still called (even though its result
  // is unused now) because it's what actually refreshes/sets the session
  // cookie via the `setAll` callback above.
  await supabase.auth.getClaims();

  // IMPORTANT: must return supabaseResponse as-is (or copy its cookies onto
  // any replacement response) — otherwise the browser and server auth state
  // can go out of sync and terminate the user's session prematurely.
  return supabaseResponse;
}
