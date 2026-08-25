import { redirect } from 'next/navigation';

/**
 * TrueBrief behaves like ChatGPT: there's no marketing landing page at "/".
 * Visitors land directly in the app shell. Signed-out visitors see the same
 * shell with a "Sign in to start tracking" prompt (per-page, see the
 * (app)/* pages) instead of a hard auth-gate redirect.
 */
export default function RootPage() {
  redirect('/topics/new');
}
