'use client';

import { SignUp } from "@clerk/nextjs";
import { useIsNativeApp } from "@/hooks/useIsNativeApp";

export default function Page() {
  // Google OAuth blocks embedded webviews — inside the native app, Google
  // sign-up bounces to the system browser with no way back into the app.
  // Hide it there and keep it on web, where it works normally.
  //
  // See sign-in/page.tsx for the two real bugs this fix went through:
  // (1) appearance must be set before first mount (Clerk doesn't react to it
  // changing later), (2) a className loses the cascade fight against Clerk's
  // own injected CSS — a style object wins because it goes through Clerk's
  // own styling engine instead.
  const isNativeApp = useIsNativeApp();
  if (isNativeApp === null) return <div className="min-h-screen bg-slate-50" />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignUp
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
