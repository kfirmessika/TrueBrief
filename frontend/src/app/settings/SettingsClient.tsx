'use client';

import { useState } from 'react';
import { useClerk } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import {
  User, CreditCard, Bell, Trash2, LogOut, ExternalLink,
  Shield, ChevronRight, Check
} from 'lucide-react';
import PushNotificationToggle from '@/components/PushNotificationToggle';
import { useApi } from '@/lib/useApi';
import { FadeIn } from '@/components/ui/motion';
import { cn } from '@/lib/utils';

interface Props {
  email: string;
  name: string;
  tier: string;
  billingStatus: string;
  periodEnd: number | null;
}

// ── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-widest px-1">{title}</h2>
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] divide-y divide-[var(--color-border)] overflow-hidden">
        {children}
      </div>
    </section>
  );
}

function Row({ label, value, action, danger }: {
  label: string;
  value?: string;
  action?: React.ReactNode;
  danger?: boolean;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3.5 gap-4">
      <div className="min-w-0">
        <p className={cn('text-sm font-medium', danger ? 'text-[var(--color-danger)]' : 'text-[var(--color-text)]')}>{label}</p>
        {value && <p className="text-xs text-[var(--color-text-muted)] mt-0.5">{value}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

const TIER_LABELS: Record<string, string> = {
  free: 'Free',
  pro: 'Pro',
  power: 'Power',
};

export default function SettingsClient({ email, name, tier, billingStatus, periodEnd }: Props) {
  const { signOut } = useClerk();
  const router = useRouter();
  const api = useApi();
  const [deleting, setDeleting] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);

  const handleSignOut = () => signOut(() => router.push('/'));

  const handleBillingPortal = async () => {
    setPortalLoading(true);
    try {
      const res = await api.post('/billing/portal', { return_url: window.location.href });
      window.location.href = res.data.portal_url;
    } catch {
      alert('Could not open billing portal. Contact support.');
    } finally {
      setPortalLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    const confirmed = window.confirm(
      'This will permanently delete your account, all topics, briefs, and data. This cannot be undone.\n\nType OK to confirm.'
    );
    if (!confirmed) return;
    setDeleting(true);
    try {
      await api.delete('/users/me');
      await signOut();
      router.push('/');
    } catch {
      alert('Failed to delete account. Please contact support@truebrief.io.');
      setDeleting(false);
    }
  };

  const periodEndDate = periodEnd
    ? new Date(periodEnd * 1000).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : null;

  return (
    <FadeIn className="max-w-xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      <h1 className="text-2xl font-bold text-[var(--color-text)]">Settings</h1>

      {/* Account */}
      <Section title="Account">
        <Row label="Email" value={email} />
        {name && <Row label="Name" value={name} />}
        <Row
          label="Sign out"
          action={
            <button
              onClick={handleSignOut}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-danger)] transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          }
        />
      </Section>

      {/* Subscription */}
      <Section title="Subscription">
        <Row
          label="Current plan"
          value={billingStatus === 'active' && periodEndDate ? `Renews ${periodEndDate}` : 'No active subscription'}
          action={
            <span className={cn(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold',
              tier === 'free'
                ? 'bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)]'
                : 'bg-[var(--color-brand-subtle)] text-[var(--color-brand)]'
            )}>
              {tier !== 'free' && <Check className="h-3 w-3" />}
              {TIER_LABELS[tier] ?? tier}
            </span>
          }
        />
        {tier === 'free' ? (
          <Row
            label="Upgrade to Pro"
            value="More topics, faster scans, premium sources"
            action={
              <a
                href="/pricing"
                className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--color-brand)] hover:underline"
              >
                View plans <ChevronRight className="h-3.5 w-3.5" />
              </a>
            }
          />
        ) : (
          <Row
            label="Manage billing"
            value="Invoices, payment method, cancel"
            action={
              <button
                onClick={handleBillingPortal}
                disabled={portalLoading}
                className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--color-brand)] hover:underline disabled:opacity-50"
              >
                {portalLoading ? 'Opening…' : 'Manage billing'}
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
            }
          />
        )}
      </Section>

      {/* Notifications */}
      <Section title="Notifications">
        <div className="px-4 py-3">
          <PushNotificationToggle />
        </div>
      </Section>

      {/* Danger zone */}
      <Section title="Danger zone">
        <Row
          label="Delete account"
          value="Permanently remove all your data"
          danger
          action={
            <button
              onClick={handleDeleteAccount}
              disabled={deleting}
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-[var(--color-danger)] hover:underline disabled:opacity-50"
            >
              <Trash2 className="h-4 w-4" />
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          }
        />
      </Section>
    </FadeIn>
  );
}
