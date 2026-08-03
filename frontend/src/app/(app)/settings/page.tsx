'use client';

import { useSession } from '@/app/providers';
import { createClient } from '@/lib/supabase/client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useRouter } from 'next/navigation';
import { useState, useMemo } from 'react';
import type { ApiKey, ApiKeyUsage } from '@/lib/api';
import { useTier } from '@/hooks/useTier';
import { getTimezone, setTimezone, listTimezones, tzShortLabel } from '@/lib/timezone';

interface UserStats {
  total_briefs: number;
  articles_scanned: number;
  time_saved_minutes: number;
}

const row: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 0', borderBottom: '0.5px solid var(--color-border-tertiary)',
};
const label: React.CSSProperties = { fontSize: 13, color: 'var(--color-text-secondary)' };
const value: React.CSSProperties = { fontSize: 13, color: 'var(--color-text-primary)', fontWeight: 500 };
const card: React.CSSProperties = {
  border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12,
  padding: '0 16px', marginBottom: 16,
};
const smallBtn: React.CSSProperties = {
  fontSize: 12, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
  background: 'transparent', color: 'var(--color-text-secondary)',
  border: '0.5px solid var(--color-border-secondary)', fontFamily: 'inherit',
};
const primaryBtn: React.CSSProperties = {
  fontSize: 12, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
  background: 'var(--color-text-primary)', color: 'var(--color-background-primary, #fff)',
  border: 'none', fontFamily: 'inherit',
};

// ── Billing section ──────────────────────────────────────────────────────────

// Scan schedules are stored and run in UTC; this only controls how times are shown and
// entered on the topic page. Defaults to whatever zone the browser reports, so it is
// already correct for most people without ever opening this setting — the picker is for
// the case where the browser is wrong (travel, a VPS, a shared machine).
function TimezoneSection() {
  const [tz, setTz] = useState(getTimezone);
  const zones = useMemo(() => listTimezones(), []);
  const [saved, setSaved] = useState(false);

  const change = (next: string) => {
    setTz(next);
    setTimezone(next);
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  };

  return (
    <div style={card}>
      <div style={{ ...row, borderBottom: 'none', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <span style={label}>Time zone</span>
          <p style={{ fontSize: 11, color: 'var(--color-text-tertiary)', margin: '2px 0 0' }}>
            Scan times are shown and entered in this zone ({tzShortLabel(tz)}).
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {saved && <span style={{ fontSize: 11, color: 'var(--tb-green)' }}>Saved</span>}
          <select
            value={tz}
            onChange={(e) => change(e.target.value)}
            style={{
              fontSize: 12, padding: '4px 8px', borderRadius: 6, maxWidth: 220,
              border: '0.5px solid var(--color-border-secondary)',
              background: 'var(--color-background-primary)',
              color: 'var(--color-text-primary)',
            }}
          >
            {zones.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}

function BillingSection() {
  const api = useApi();
  const { data: billing } = useTier();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const tier = billing?.tier ?? 'free';
  const isPaid = tier === 'pro' || tier === 'power';

  const startCheckout = async (target: 'pro' | 'power') => {
    setBusy(true); setError('');
    try {
      const origin = window.location.origin;
      const { data } = await api.post('/billing/checkout', {
        tier: target,
        success_url: `${origin}/settings?upgraded=1`,
        cancel_url: `${origin}/settings`,
      });
      window.location.href = data.checkout_url;
    } catch {
      setError('Could not start checkout — is billing configured?');
      setBusy(false);
    }
  };

  const openPortal = async () => {
    setBusy(true); setError('');
    try {
      const { data } = await api.post('/billing/portal', {
        return_url: `${window.location.origin}/settings`,
      });
      window.location.href = data.portal_url;
    } catch {
      setError('Could not open the billing portal.');
      setBusy(false);
    }
  };

  return (
    <div style={card}>
      <div style={row}>
        <span style={label}>Plan</span>
        <span style={{
          fontSize: 11, padding: '2px 10px', borderRadius: 10, fontWeight: 600,
          textTransform: 'capitalize',
          background: isPaid ? 'var(--tb-green)' : 'var(--color-background-info)',
          color: isPaid ? '#fff' : 'var(--color-text-info)',
        }}>
          {tier}
        </span>
      </div>
      {!isPaid && (
        <div style={row}>
          <span style={label}>Upgrade for more topics, faster scans, and API access</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button disabled={busy} onClick={() => startCheckout('pro')} style={primaryBtn}>
              {busy ? '…' : 'Go Pro'}
            </button>
            <button disabled={busy} onClick={() => startCheckout('power')} style={smallBtn}>
              Go Power
            </button>
          </div>
        </div>
      )}
      {isPaid && (
        <div style={row}>
          <span style={label}>Subscription, invoices, payment method</span>
          <button disabled={busy} onClick={openPortal} style={smallBtn}>
            {busy ? '…' : 'Manage billing'}
          </button>
        </div>
      )}
      <div style={{ ...row, borderBottom: 'none' }}>
        <span style={label}>Topics allowed</span>
        <span style={value}>
          {billing ? (billing.limits.max_topics === -1 ? 'Unlimited' : billing.limits.max_topics) : '—'}
        </span>
      </div>
      {error && (
        <p style={{ fontSize: 12, color: '#B45309', padding: '0 0 12px', margin: 0 }}>{error}</p>
      )}
    </div>
  );
}

// ── API keys section ─────────────────────────────────────────────────────────

function ApiKeysSection() {
  const api = useApi();
  const qc = useQueryClient();
  const { data: billing } = useTier();
  const [name, setName] = useState('');
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const hasApiAccess = (billing?.limits?.api_calls_per_day ?? 0) !== 0;

  const { data: keysData } = useQuery<{ keys: ApiKey[] }>({
    queryKey: ['api-keys'],
    queryFn: async () => (await api.get('/api-keys')).data,
    enabled: hasApiAccess,
    staleTime: 60_000,
  });

  const { data: usage } = useQuery<ApiKeyUsage>({
    queryKey: ['api-keys-usage'],
    queryFn: async () => (await api.get('/api-keys/usage')).data,
    enabled: hasApiAccess,
    staleTime: 60_000,
  });

  const createKey = useMutation({
    mutationFn: async () =>
      (await api.post('/api-keys', { name: name.trim() || 'default' })).data,
    onSuccess: (data: { key: string }) => {
      setNewKey(data.key);
      setName('');
      setError('');
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Could not create the key.');
    },
  });

  const revokeKey = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  });

  const copyKey = async () => {
    if (!newKey) return;
    await navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const activeKeys = (keysData?.keys ?? []).filter((k) => !k.revoked_at);

  if (!hasApiAccess) {
    return (
      <div style={card}>
        <div style={{ ...row, borderBottom: 'none' }}>
          <div>
            <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 2px' }}>
              Developer API
            </p>
            <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: 0 }}>
              Programmatic access to your verified fact stream. Available on Pro and Power plans.
            </p>
          </div>
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 10,
            background: 'var(--color-background-info)', color: 'var(--color-text-info)',
            whiteSpace: 'nowrap',
          }}>
            Pro feature
          </span>
        </div>
      </div>
    );
  }

  return (
    <div style={card}>
      <div style={{ ...row, borderBottom: activeKeys.length || newKey ? undefined : 'none' }}>
        <div>
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 2px' }}>
            Developer API
          </p>
          <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: 0 }}>
            {usage
              ? `${usage.calls_used} / ${usage.daily_limit === -1 ? '∞' : usage.daily_limit} calls today · `
              : ''}
            <a href="/developers" target="_blank" style={{ color: 'var(--tb-green)', textDecoration: 'none' }}>
              API docs →
            </a>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Key name"
            maxLength={60}
            style={{
              fontSize: 12, padding: '4px 10px', borderRadius: 8, width: 110,
              border: '0.5px solid var(--color-border-secondary)',
              background: 'transparent', color: 'var(--color-text-primary)',
              fontFamily: 'inherit', outline: 'none',
            }}
          />
          <button
            onClick={() => createKey.mutate()}
            disabled={createKey.isPending}
            style={primaryBtn}
          >
            {createKey.isPending ? '…' : 'Create key'}
          </button>
        </div>
      </div>

      {error && (
        <p style={{ fontSize: 12, color: '#B45309', padding: '10px 0', margin: 0, borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
          {error}
        </p>
      )}

      {newKey && (
        <div style={{ padding: '12px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: '#B45309', margin: '0 0 6px' }}>
            Copy this key now — it won&apos;t be shown again.
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <code style={{
              fontSize: 11, padding: '6px 10px', borderRadius: 8, flex: 1,
              background: 'var(--color-background-tertiary)', color: 'var(--color-text-primary)',
              wordBreak: 'break-all',
            }}>
              {newKey}
            </code>
            <button onClick={copyKey} style={smallBtn}>{copied ? 'Copied ✓' : 'Copy'}</button>
            <button onClick={() => setNewKey(null)} style={smallBtn}>Done</button>
          </div>
        </div>
      )}

      {activeKeys.map((k, i) => (
        <div key={k.id} style={{ ...row, borderBottom: i === activeKeys.length - 1 ? 'none' : undefined }}>
          <div>
            <span style={{ ...value, marginRight: 8 }}>{k.name}</span>
            <code style={{ fontSize: 11, color: 'var(--color-text-tertiary)' }}>{k.key_prefix}…</code>
          </div>
          <button
            onClick={() => revokeKey.mutate(k.id)}
            disabled={revokeKey.isPending}
            style={{ ...smallBtn, color: '#B91C1C', borderColor: '#FCCACA' }}
          >
            Revoke
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user } = useSession();
  const router = useRouter();
  // Created inside the handler, not via useMemo — createClient() must never
  // run during SSR/static prerendering.
  const signOut = async () => {
    await createClient().auth.signOut();
    router.push('/sign-in');
  };
  const api = useApi();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { data: billing } = useTier();

  const { data: stats } = useQuery<UserStats>({
    queryKey: ['user-stats'],
    queryFn: async () => (await api.get('/users/me/stats')).data,
    staleTime: 60_000,
  });

  const deleteAccount = useMutation({
    mutationFn: () => api.delete('/users/me'),
    onSuccess: () => signOut(),
  });

  // Google OAuth populates user_metadata.full_name / .name; email-OTP users have neither.
  const fullName: string =
    (user?.user_metadata?.full_name as string | undefined) ||
    (user?.user_metadata?.name as string | undefined) ||
    '';
  const email = user?.email ?? '';
  const displayName = fullName || email;
  const nameParts = fullName.trim().split(/\s+/).filter(Boolean);
  const initials = nameParts.length >= 2
    ? `${nameParts[0][0]}${nameParts[1][0]}`
    : nameParts[0]?.[0]?.toUpperCase() ?? email[0]?.toUpperCase() ?? '?';

  const tier = billing?.tier ?? 'free';

  return (
    <div style={{ flex: 1, padding: '20px 22px 40px', maxWidth: 560 }}>
      <p style={{ fontSize: 20, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 24px' }}>
        Settings
      </p>

      {/* Account */}
      <div style={card}>
        <div style={{ ...row, alignItems: 'flex-start', paddingTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%', background: 'var(--tb-green)',
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 500,
            }}>
              {initials}
            </div>
            <div>
              <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>{displayName}</p>
              <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: 0 }}>{email}</p>
            </div>
          </div>
          <span style={{
            fontSize: 10, padding: '2px 8px', borderRadius: 10, textTransform: 'capitalize',
            background: 'var(--color-background-info)', color: 'var(--color-text-info)',
          }}>
            {tier}
          </span>
        </div>

        <div style={row}>
          <span style={label}>Briefs delivered</span>
          <span style={value}>{stats?.total_briefs ?? '—'}</span>
        </div>
        <div style={row}>
          <span style={label}>Articles scanned</span>
          <span style={value}>{stats?.articles_scanned ?? '—'}</span>
        </div>
        <div style={{ ...row, borderBottom: 'none' }}>
          <span style={label}>Time saved</span>
          <span style={value}>{stats ? `${stats.time_saved_minutes} min` : '—'}</span>
        </div>
      </div>

      {/* Preferences */}
      <TimezoneSection />

      {/* Billing */}
      <BillingSection />

      {/* Developer API */}
      <ApiKeysSection />

      {/* Actions */}
      <div style={card}>
        <div style={{ ...row, borderBottom: 'none' }}>
          <span style={label}>Sign out</span>
          <button onClick={() => signOut()} style={smallBtn}>
            Sign out
          </button>
        </div>
      </div>

      {/* Danger zone */}
      <div style={{
        border: '0.5px solid #FCCACA', borderRadius: 12,
        padding: '0 16px',
      }}>
        <div style={{ ...row, borderBottom: 'none' }}>
          <div>
            <p style={{ fontSize: 13, fontWeight: 500, color: '#B91C1C', margin: '0 0 2px' }}>Delete account</p>
            <p style={{ fontSize: 12, color: 'var(--color-text-tertiary)', margin: 0 }}>
              Permanently removes all your data.
            </p>
          </div>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              style={{ ...smallBtn, color: '#B91C1C', borderColor: '#FCCACA' }}
            >
              Delete
            </button>
          ) : (
            <button
              onClick={() => deleteAccount.mutate()}
              disabled={deleteAccount.isPending}
              style={{
                fontSize: 12, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
                background: '#B91C1C', color: '#fff', border: 'none', fontFamily: 'inherit',
              }}
            >
              {deleteAccount.isPending ? 'Deleting…' : 'Confirm delete'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
