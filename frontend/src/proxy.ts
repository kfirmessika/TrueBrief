import { type NextRequest } from 'next/server';
import { updateSession } from '@/lib/supabase/proxy';

export default async function proxy(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: ['/((?!.*\\..*|_next).*)', '/', '/(api|trpc)(.*)'],
};
