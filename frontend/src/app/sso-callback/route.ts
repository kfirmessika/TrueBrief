import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@/lib/supabase/server';

/**
 * Completes both the plain web OAuth/magic-link flow (Supabase/Google
 * redirect here directly with ?code=...) AND the native-app flow
 * (NativeShell's appUrlOpen listener forwards the custom-scheme callback
 * here via an in-webview navigation).
 *
 * This MUST be a server Route Handler, not a client page. `createBrowserClient()`
 * defaults `detectSessionInUrl: true`, so a fresh client instance on this page
 * would auto-detect `?code=` and race its own internal exchange against an
 * explicit `exchangeCodeForSession()` call — whichever wins deletes the PKCE
 * verifier cookie first, and the other fails with "PKCE code verifier not
 * found in storage." The server client has no such auto-detection, so there's
 * no race: this is Supabase's own documented Next.js App Router pattern.
 */
export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code');

  // Behind Railway's reverse proxy, request.nextUrl.origin reflects the
  // container's internal bind address (localhost:8080), not the public
  // domain the browser actually used. Derive it from the forwarded headers
  // instead -- the same pattern Supabase's own docs use for this exact
  // load-balancer situation.
  const forwardedHost = request.headers.get('x-forwarded-host') ?? request.headers.get('host');
  const forwardedProto = request.headers.get('x-forwarded-proto') ?? 'https';
  const origin = forwardedHost ? `${forwardedProto}://${forwardedHost}` : request.nextUrl.origin;

  if (!code) {
    return NextResponse.redirect(`${origin}/sign-in?error=Missing authorization code.`);
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(`${origin}/sign-in?error=${encodeURIComponent(error.message)}`);
  }

  return NextResponse.redirect(`${origin}/dashboard`);
}
