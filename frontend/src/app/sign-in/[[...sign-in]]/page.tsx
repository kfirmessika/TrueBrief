'use client';

import { SignIn } from "@clerk/nextjs";
import { useIsNativeApp } from "@/hooks/useIsNativeApp";

export default function Page() {
  // Google OAuth blocks embedded webviews — inside the native app, Google
  // sign-in bounces to the system browser with no way back into the app.
  // Hide it there and keep it on web, where it works normally.
  //
  // Clerk's <SignIn> mounts its internal widget once and does not react to
  // `appearance` changing afterwards, so we must not render it until we know
  // whether we're native — otherwise it mounts once with Google visible and
  // never re-checks. Blank pane for one tick instead of a flash of the wrong UI.
  //
  // A className ('hidden') here loses the cascade fight against Clerk's own
  // injected CSS (Tailwind's plain `.hidden{display:none}` has no more
  // specificity than Clerk's `.cl-socialButtonsRoot{display:flex}` — verified
  // live in a running app: the class WAS applied, computed display was still
  // `flex`). A style object goes through Clerk's own styling engine instead
  // and actually wins.
  const isNativeApp = useIsNativeApp();
  if (isNativeApp === null) return <div className="min-h-screen bg-slate-50" />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignIn
        appearance={isNativeApp ? {
          elements: {
            socialButtonsRoot: { display: 'none' },
            dividerRow: { display: 'none' },
          },
        } : undefined}
      />
    </div>
  );
}
