'use client';

import { SignIn } from "@clerk/nextjs";
import { useIsNativeApp } from "@/hooks/useIsNativeApp";

export default function Page() {
  // Google OAuth blocks embedded webviews — inside the native app, Google
  // sign-in bounces to the system browser with no way back into the app.
  // Hide it there and keep it on web, where it works normally.
  const isNativeApp = useIsNativeApp();

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <SignIn
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
