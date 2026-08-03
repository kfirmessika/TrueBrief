'use client';

import { SignUp } from "@clerk/nextjs";
import { useIsNativeApp } from "@/hooks/useIsNativeApp";
import NativeGoogleButton from "@/components/native/NativeGoogleButton";

export default function Page() {
  // See sign-in/page.tsx for the full rationale — same mechanism, sign-up flow.
  const isNativeApp = useIsNativeApp();
  if (isNativeApp === null) return <div className="min-h-screen bg-slate-50" />;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50">
      {isNativeApp && (
        <div style={{ width: '100%', maxWidth: 400, marginBottom: 12 }}>
          <NativeGoogleButton mode="sign-up" />
        </div>
      )}
      <SignUp
        appearance={{
          elements: isNativeApp ? {
            socialButtonsRoot: { display: 'none' },
            dividerRow: { display: 'none' },
          } : undefined,
          options: { unsafe_disableDevelopmentModeWarnings: true },
        }}
      />
    </div>
  );
}
