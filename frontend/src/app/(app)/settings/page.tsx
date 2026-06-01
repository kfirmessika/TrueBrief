'use client';

import { useUser, useClerk } from '@clerk/nextjs';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { useState } from 'react';

interface UserStats {
  total_briefs: number;
  articles_scanned: number;
  time_saved_minutes: number;
}

export default function SettingsPage() {
  const { user } = useUser();
  const { signOut } = useClerk();
  const api = useApi();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: stats } = useQuery<UserStats>({
    queryKey: ['user-stats'],
    queryFn: async () => (await api.get('/users/me/stats')).data,
    staleTime: 60_000,
  });

  const deleteAccount = useMutation({
    mutationFn: () => api.delete('/users/me'),
    onSuccess: () => signOut(),
  });

  const displayName = user?.firstName
    ? `${user.firstName} ${user.lastName ?? ''}`.trim()
    : user?.emailAddresses?.[0]?.emailAddress ?? '';
  const email = user?.emailAddresses?.[0]?.emailAddress ?? '';
  const initials = user?.firstName && user?.lastName
    ? `${user.firstName[0]}${user.lastName[0]}`
    : (user?.firstName?.[0] ?? email[0]?.toUpperCase() ?? '?');

  const row: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 0', borderBottom: '0.5px solid var(--color-border-tertiary)',
  };
  const label: React.CSSProperties = { fontSize: 13, color: 'var(--color-text-secondary)' };
  const value: React.CSSProperties = { fontSize: 13, color: 'var(--color-text-primary)', fontWeight: 500 };

  return (
    <div style={{ flex: 1, padding: '20px 22px 40px', maxWidth: 560 }}>
      <p style={{ fontSize: 20, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 24px' }}>
        Settings
      </p>

      {/* Account */}
      <div style={{
        border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12,
        padding: '0 16px', marginBottom: 16,
      }}>
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
            fontSize: 10, padding: '2px 8px', borderRadius: 10,
            background: 'var(--color-background-info)', color: 'var(--color-text-info)',
          }}>
            Free
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

      {/* Actions */}
      <div style={{
        border: '0.5px solid var(--color-border-tertiary)', borderRadius: 12,
        padding: '0 16px', marginBottom: 16,
      }}>
        <div style={row}>
          <span style={label}>Plan</span>
          <button style={{
            fontSize: 12, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
            background: 'var(--color-text-primary)', color: '#fff', border: 'none',
            fontFamily: 'inherit',
          }}>
            Upgrade to Pro
          </button>
        </div>
        <div style={{ ...row, borderBottom: 'none' }}>
          <span style={label}>Sign out</span>
          <button
            onClick={() => signOut()}
            style={{
              fontSize: 12, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
              background: 'transparent', color: 'var(--color-text-secondary)',
              border: '0.5px solid var(--color-border-secondary)', fontFamily: 'inherit',
            }}
          >
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
              style={{
                fontSize: 12, padding: '4px 12px', borderRadius: 8, cursor: 'pointer',
                background: 'transparent', color: '#B91C1C',
                border: '0.5px solid #FCCACA', fontFamily: 'inherit',
              }}
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
