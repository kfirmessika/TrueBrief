import { Metadata } from 'next';
import { auth, currentUser } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import { apiFetch } from '@/lib/api';
import SettingsClient from './SettingsClient';

export const metadata: Metadata = {
  title: 'Settings | TrueBrief',
};

export default async function SettingsPage() {
  const { userId } = await auth();
  if (!userId) redirect('/sign-in');

  const user = await currentUser();

  // Fetch billing status (non-blocking)
  let billing: { tier: string; status: string; current_period_end: number | null } | null = null;
  try {
    const res = await apiFetch('/billing/status');
    if (res.ok) billing = await res.json();
  } catch { /* ignore */ }

  return (
    <SettingsClient
      email={user?.emailAddresses[0]?.emailAddress ?? ''}
      name={user?.fullName ?? user?.firstName ?? ''}
      tier={billing?.tier ?? 'free'}
      billingStatus={billing?.status ?? 'none'}
      periodEnd={billing?.current_period_end ?? null}
    />
  );
}
