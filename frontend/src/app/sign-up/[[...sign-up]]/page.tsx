'use client';

import { SignUp } from "@clerk/nextjs";
import { useIsNativeApp } from "@/hooks/useIsNativeApp";

export default function Page() {
  // Google OAuth blocks embedded webviews — inside the native app, Google
  // sign-up bounces to the system browser with no way back into the app.
  // Hide it there and keep it on web, where it works normally.
  //
  // Clerk's <SignUp> mounts its internal widget once and does not react to
  // `appearance` changing afterwards, so we must not render it until we know
  // whether we're native — otherwise it mounts once with Google visible and
  // never re-checks. Blank pane for one tick instead of a flash of the wrong UI.
  const isNativeApp = useIsNativeApp();
  if (isNativeApp === null) return <div className="min-h-screen bg-slate-50" />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignUp
        appearance={isNativeApp ? {
          elements: {
            socialButtonsRoot: 'hidden',
            dividerRow: 'hidden',
          },
        } : undefined}
      />
    </div>
  );
}
