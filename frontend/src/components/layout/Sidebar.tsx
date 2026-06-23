'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUser } from '@clerk/nextjs';
import { useApi } from '@/lib/useApi';
import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Plus, Search, LayoutGrid, Settings, MoreHorizontal, ScanSearch, Trash2, BarChart2,
} from 'lucide-react';

interface Topic {
  id: string;
  raw_query: string;
  is_active: boolean;
  last_scan_at?: string | null;
  frequency?: string;
  is_scanning?: boolean;
}

function StatusDot({ topic }: { topic: Topic }) {
  const isScanning = !!topic.is_scanning;  // live signal from the backend (scan_started_at)
  if (isScanning) return (
    <span title="Scanning…" style={{
      width: 7, height: 7, borderRadius: '50%', flexShrink: 0, display: 'inline-block',
      background: 'var(--tb-amber)', animation: 'tb-pulse 1.5s ease-in-out infinite',
    }} />
  );
  return (
    <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, display: 'inline-block', background: 'var(--color-border-secondary)' }} />
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useUser();
  const api = useApi();

  const queryClient = useQueryClient();
  const [hoveredTopic, setHoveredTopic] = useState<string | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const { data: topics = [] } = useQuery<Topic[]>({
    queryKey: ['topics'],
    queryFn: async () => {
      const r = await api.get('/topics');
      return r.data;
    },
    staleTime: 10_000,
    refetchInterval: 8_000,          // keep the per-topic scanning dot live
    refetchOnWindowFocus: true,
  });

  const deleteTopic = useMutation({
    mutationFn: (id: string) => api.delete(`/topics/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['topics'] }),
  });

  const [scanError, setScanError] = useState<string | null>(null);

  const scanTopic = useMutation({
    mutationFn: (id: string) => api.post<{ task_id: string }>(`/topics/${id}/scan`),
    onSuccess: (data, topicId) => {
      setScanError(null);
      if (data?.data?.task_id) {
        localStorage.setItem(`scan_task_${topicId}`, data.data.task_id);
      }
      // Backend stamped scan_started_at — refresh topics so the dot lights up now.
      queryClient.invalidateQueries({ queryKey: ['topics'] });
    },
    onError: (err: any, topicId) => {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail ?? '';
      if (status === 429) {
        // Parse "next scan available in X hours" from detail if present
        const hoursMatch = detail.match(/(\d+(?:\.\d+)?)\s*hour/i);
        const msg = hoursMatch
          ? `Next scan available in ${Math.ceil(parseFloat(hoursMatch[1]))}h (plan limit)`
          : 'Scan rate limit reached. Upgrade for more frequent scans.';
        setScanError(topicId + ':' + msg);
        setTimeout(() => setScanError(null), 5000);
      }
    },
  });

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenu(null);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const isDashboard = pathname === '/dashboard';
  const isNewTopic  = pathname === '/topics/new';
  const activeTopic = pathname.startsWith('/topics/') && !isNewTopic
    ? pathname.split('/topics/')[1]?.split('/')[0]
    : null;

  const initials = user?.firstName && user?.lastName
    ? `${user.firstName[0]}${user.lastName[0]}`
    : user?.firstName?.[0] ?? user?.emailAddresses?.[0]?.emailAddress?.[0]?.toUpperCase() ?? '?';
  const displayName = user?.firstName
    ? `${user.firstName} ${user.lastName ?? ''}`.trim()
    : user?.emailAddresses?.[0]?.emailAddress ?? '';

  const navItem = (label: string): React.CSSProperties => ({
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '8px 12px', margin: '2px 8px', borderRadius: 8, cursor: 'pointer',
    fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)',
    background: 'transparent',
  });

  return (
    <div style={{
      width: 232, minWidth: 232,
      borderRight: '0.5px solid var(--color-border-tertiary)',
      background: 'var(--color-background-secondary)',
      display: 'flex', flexDirection: 'column',
      overflowY: 'auto', height: '100%',
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500, fontSize: 14, color: 'var(--color-text-primary)', padding: '14px 14px 10px' }}>
        <div style={{ width: 26, height: 26, background: 'var(--tb-green)', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 500, flexShrink: 0 }}>
          TB
        </div>
        TrueBrief
      </div>

      {/* New topic button */}
      <button
        onClick={() => router.push('/topics/new')}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          margin: '2px 10px 6px', padding: '7px 12px',
          border: isNewTopic ? '0.5px solid var(--tb-green-border)' : '0.5px solid var(--color-border-secondary)',
          borderRadius: 8, cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
          background: isNewTopic ? 'var(--tb-green-light)' : 'var(--color-background-primary)',
          color: isNewTopic ? 'var(--tb-green-dark)' : 'var(--color-text-secondary)',
          fontWeight: isNewTopic ? 500 : 400,
          width: 'calc(100% - 20px)',
        }}
      >
        <Plus size={14} />
        New topic
      </button>

      {/* Search */}
      <div style={{
        margin: '0 10px 6px', padding: '6px 10px',
        border: '0.5px solid var(--color-border-tertiary)', borderRadius: 8,
        fontSize: 12, color: 'var(--color-text-tertiary)',
        display: 'flex', alignItems: 'center', gap: 7,
        background: 'var(--color-background-primary)',
      }}>
        <Search size={12} style={{ flexShrink: 0 }} />
        <span>Search briefs...</span>
      </div>

      <hr style={{ border: 'none', borderTop: '0.5px solid var(--color-border-tertiary)', margin: '4px 10px' }} />

      {/* Dashboard */}
      <div
        onClick={() => router.push('/dashboard')}
        style={{
          ...navItem('Dashboard'),
          background: isDashboard ? 'var(--color-background-primary)' : 'transparent',
        }}
        onMouseEnter={e => { if (!isDashboard) (e.currentTarget as HTMLDivElement).style.background = 'var(--color-background-tertiary)'; }}
        onMouseLeave={e => { if (!isDashboard) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <LayoutGrid size={14} color="var(--color-text-secondary)" />
          Dashboard
        </div>
      </div>

      <hr style={{ border: 'none', borderTop: '0.5px solid var(--color-border-tertiary)', margin: '4px 10px' }} />

      {/* My Topics */}
      <div style={{ fontSize: 10, color: 'var(--color-text-tertiary)', padding: '10px 14px 3px', letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500 }}>
        My topics
      </div>

      {topics.map(topic => {
        const isActive = activeTopic === topic.id;
        const isHovered = hoveredTopic === topic.id;
        const menuOpen = openMenu === topic.id;
        return (
          <div
            key={topic.id}
            onClick={() => router.push(`/topics/${topic.id}`)}
            onMouseEnter={() => setHoveredTopic(topic.id)}
            onMouseLeave={() => { setHoveredTopic(null); }}
            style={{
              position: 'relative',
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 12px', margin: '1px 8px', borderRadius: 8, cursor: 'pointer',
              background: isActive ? 'var(--color-background-primary)' : (isHovered ? 'var(--color-background-tertiary)' : 'transparent'),
            }}
          >
            <StatusDot topic={topic} />
            <span style={{
              fontSize: 13, color: 'var(--color-text-primary)', flex: 1,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {topic.raw_query}
            </span>

            {/* 3-dots button — visible only on hover or when menu is open */}
            {(isHovered || menuOpen) && (
              <button
                onClick={e => { e.stopPropagation(); setOpenMenu(menuOpen ? null : topic.id); }}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 2px',
                  borderRadius: 4, display: 'flex', alignItems: 'center', color: 'var(--color-text-secondary)',
                  flexShrink: 0,
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-border-secondary)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
              >
                <MoreHorizontal size={14} />
              </button>
            )}

            {/* Dropdown menu */}
            {menuOpen && (
              <div
                ref={menuRef}
                onClick={e => e.stopPropagation()}
                style={{
                  position: 'absolute', right: 8, top: '100%', zIndex: 100,
                  background: 'var(--color-background-primary)',
                  border: '1px solid var(--color-border-secondary)',
                  borderRadius: 8, padding: '4px', minWidth: 130,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                }}
              >
                <button
                  onClick={() => { scanTopic.mutate(topic.id); setOpenMenu(null); }}
                  style={{
                    width: '100%', background: 'none', border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '7px 10px', borderRadius: 6,
                    fontSize: 13, color: 'var(--color-text-primary)', textAlign: 'left',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-background-tertiary)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
                >
                  <ScanSearch size={13} />
                  Scan
                </button>
                {scanError?.startsWith(topic.id + ':') && (
                  <div style={{ fontSize: 11, color: '#B45309', padding: '2px 10px 6px', lineHeight: 1.4 }}>
                    {scanError.slice(topic.id.length + 1)}
                  </div>
                )}
                <button
                  onClick={() => { if (confirm(`Delete "${topic.raw_query}"?`)) { deleteTopic.mutate(topic.id); setOpenMenu(null); } }}
                  style={{
                    width: '100%', background: 'none', border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '7px 10px', borderRadius: 6,
                    fontSize: 13, color: 'var(--tb-coral-dot)', textAlign: 'left',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-background-tertiary)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
                >
                  <Trash2 size={13} />
                  Delete
                </button>
              </div>
            )}
          </div>
        );
      })}

      {topics.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', padding: '8px 14px', fontStyle: 'italic' }}>
          No topics yet
        </div>
      )}

      {/* Footer */}
      <div style={{ marginTop: 'auto', borderTop: '0.5px solid var(--color-border-tertiary)', padding: 6 }}>
        <div
          onClick={() => router.push('/admin')}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 8px', borderRadius: 8, cursor: 'pointer', fontSize: 12, color: pathname === '/admin' ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)', background: pathname === '/admin' ? 'var(--color-background-tertiary)' : 'transparent' }}
          onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-background-tertiary)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = pathname === '/admin' ? 'var(--color-background-tertiary)' : 'transparent'; }}
        >
          <BarChart2 size={14} />
          Admin
        </div>
        <div
          onClick={() => router.push('/settings')}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 8px', borderRadius: 8, cursor: 'pointer', fontSize: 12, color: 'var(--color-text-secondary)' }}
          onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'var(--color-background-tertiary)'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
        >
          <Settings size={14} />
          Settings
        </div>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 8px', borderRadius: 8, cursor: 'default', fontSize: 12, color: 'var(--color-text-secondary)' }}
        >
          <div style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--tb-green)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 500, flexShrink: 0 }}>
            {initials}
          </div>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{displayName}</span>
          <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--color-background-info)', color: 'var(--color-text-info)', flexShrink: 0 }}>
            Free
          </span>
        </div>
      </div>
    </div>
  );
}
