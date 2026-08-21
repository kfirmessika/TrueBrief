'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useApi } from '@/lib/useApi';
import { Plus, Globe2, MoreHorizontal, ScanSearch, Pencil, Trash2 } from 'lucide-react';

interface PublicTopic { id: string; name: string; subscriber_count: number; is_scanning?: boolean; }

export default function AdminPublicTopics() {
  const router = useRouter();
  const pathname = usePathname();
  const api = useApi();
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [newQuery, setNewQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [hoveredTopic, setHoveredTopic] = useState<string | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [editingTopic, setEditingTopic] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const menuRef = useRef<HTMLDivElement | null>(null);

  const { data: topics = [] } = useQuery<PublicTopic[]>({
    queryKey: ['public-topics'],
    queryFn: async () => (await api.get('/public-topics')).data,
    staleTime: 30_000,
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

  const invalidate = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['public-topics'] });
    qc.invalidateQueries({ queryKey: ['topics'] });
  }, [qc]);

  const createPublic = useMutation({
    mutationFn: async (raw_query: string) => (await api.post('/admin/public-topics', { raw_query })).data,
    onSuccess: () => {
      invalidate();
      setNewQuery('');
      setShowAdd(false);
      setError(null);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Failed to create public topic.');
    },
  });

  const scanTopic = useMutation({
    mutationFn: async (id: string) => (await api.post<{ task_id: string }>(`/topics/${id}/scan`)).data,
    onSuccess: (data, id) => {
      if (data?.task_id) localStorage.setItem(`scan_task_${id}`, data.task_id);
      invalidate();
    },
  });

  const renameTopic = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) =>
      (await api.patch(`/topics/${id}`, { name })).data,
    onSuccess: invalidate,
  });

  const deleteTopic = useMutation({
    mutationFn: async (id: string) => api.delete(`/topics/${id}`),
    onSuccess: invalidate,
  });

  const startRename = useCallback((t: PublicTopic) => {
    setEditingTopic(t.id);
    setEditValue(t.name);
    setOpenMenu(null);
  }, []);

  const submitRename = useCallback((id: string) => {
    const trimmed = editValue.trim();
    setEditingTopic(null);
    if (!trimmed) return;
    renameTopic.mutate({ id, name: trimmed });
  }, [editValue, renameTopic]);

  const submitCreate = () => {
    const q = newQuery.trim();
    if (!q || createPublic.isPending) return;
    createPublic.mutate(q);
  };

  return (
    <>
      <hr style={{ border: 'none', borderTop: '0.5px solid var(--color-border-tertiary)', margin: '4px 10px' }} />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px 3px' }}>
        <span style={{
          fontSize: 10, color: 'var(--color-text-tertiary)', letterSpacing: '0.06em',
          textTransform: 'uppercase', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <Globe2 size={11} /> Public topics
        </span>
        <button
          onClick={() => setShowAdd(v => !v)}
          title="Add a public topic"
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-tertiary)', display: 'flex', padding: 2 }}
        >
          <Plus size={13} />
        </button>
      </div>

      {showAdd && (
        <div style={{ padding: '2px 12px 8px' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              autoFocus
              value={newQuery}
              onChange={e => setNewQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') submitCreate(); }}
              placeholder="New public topic…"
              style={{
                flex: 1, fontSize: 12, padding: '6px 8px', borderRadius: 6,
                border: '0.5px solid var(--color-border-secondary)',
                background: 'var(--color-background-primary)', color: 'var(--color-text-primary)',
                fontFamily: 'inherit', boxSizing: 'border-box',
              }}
            />
            <button
              onClick={submitCreate}
              disabled={!newQuery.trim() || createPublic.isPending}
              style={{
                fontSize: 11, fontWeight: 500, padding: '0 8px', borderRadius: 6,
                border: '0.5px solid var(--tb-green)', background: 'var(--tb-green)', color: '#fff',
                cursor: newQuery.trim() ? 'pointer' : 'default', fontFamily: 'inherit',
                opacity: !newQuery.trim() || createPublic.isPending ? 0.5 : 1,
              }}
            >
              Add
            </button>
          </div>
          {error && <p style={{ fontSize: 10.5, color: '#B91C1C', margin: '4px 0 0' }}>{error}</p>}
        </div>
      )}

      {topics.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', padding: '2px 14px 8px', fontStyle: 'italic' }}>
          No public topics yet
        </div>
      )}

      {topics.map(t => {
        const isActive = pathname === `/topics/${t.id}`;
        const isHovered = hoveredTopic === t.id;
        const menuOpen = openMenu === t.id;
        return (
          <div
            key={t.id}
            onClick={() => router.push(`/topics/${t.id}`)}
            onMouseEnter={() => setHoveredTopic(t.id)}
            onMouseLeave={() => setHoveredTopic(null)}
            style={{
              position: 'relative', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 12px', margin: '1px 8px', borderRadius: 8,
              background: isActive ? 'var(--color-background-primary)' : isHovered ? 'var(--color-background-tertiary)' : 'transparent',
            }}
          >
            {/* Status dot */}
            <span style={{
              width: 7, height: 7, borderRadius: '50%', flexShrink: 0, display: 'inline-block',
              background: t.is_scanning ? 'var(--tb-amber)' : 'var(--color-border-secondary)',
              animation: t.is_scanning ? 'tb-pulse 1.5s ease-in-out infinite' : undefined,
            }} />

            {editingTopic === t.id ? (
              <input
                autoFocus
                value={editValue}
                onChange={e => setEditValue(e.target.value)}
                onClick={e => e.stopPropagation()}
                onBlur={() => submitRename(t.id)}
                onKeyDown={e => {
                  if (e.key === 'Enter') { e.preventDefault(); submitRename(t.id); }
                  if (e.key === 'Escape') { e.preventDefault(); setEditingTopic(null); }
                }}
                style={{
                  fontSize: 13, color: 'var(--color-text-primary)', flex: 1, minWidth: 0,
                  fontFamily: 'inherit', border: '0.5px solid var(--tb-green-border)',
                  borderRadius: 4, padding: '1px 4px', background: 'var(--color-background-primary)',
                }}
              />
            ) : (
              <span style={{
                fontSize: 13, color: 'var(--color-text-primary)', flex: 1,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {t.name}
              </span>
            )}

            {editingTopic !== t.id && (isHovered || menuOpen) && (
              <button
                onClick={e => { e.stopPropagation(); setOpenMenu(menuOpen ? null : t.id); }}
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

            {menuOpen && (
              <div
                ref={menuRef}
                onClick={e => e.stopPropagation()}
                style={{
                  position: 'absolute', right: 8, top: '100%', zIndex: 100,
                  background: 'var(--color-background-primary)',
                  border: '1px solid var(--color-border-secondary)',
                  borderRadius: 8, padding: '4px', minWidth: 140,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                }}
              >
                {([
                  { icon: <ScanSearch size={13} />, label: 'Scan', color: 'var(--color-text-primary)', action: () => { scanTopic.mutate(t.id); setOpenMenu(null); } },
                  { icon: <Pencil size={13} />, label: 'Rename', color: 'var(--color-text-primary)', action: () => startRename(t) },
{ icon: <Trash2 size={13} />, label: 'Delete', color: 'var(--tb-coral-dot)', action: () => { if (confirm(`Delete "${t.name}"?`)) { deleteTopic.mutate(t.id); setOpenMenu(null); } } },
                ] as { icon: React.ReactNode; label: string; color: string; action: () => void }[]).map(item => (
                  <button
                    key={item.label}
                    onClick={item.action}
                    style={{
                      width: '100%', background: 'none', border: 'none', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '7px 10px', borderRadius: 6,
                      fontSize: 13, color: item.color, textAlign: 'left', fontFamily: 'inherit',
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--color-background-tertiary)'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
                  >
                    {item.icon}{item.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}
