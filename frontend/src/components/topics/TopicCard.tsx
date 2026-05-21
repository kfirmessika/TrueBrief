'use client';

import { Topic } from '@/lib/api';
import { ScanStatusBadge } from './ScanStatusBadge';
import { Play, History, Trash2, ExternalLink, MoreVertical, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useState, useRef, useEffect } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '@/lib/utils';

interface TopicCardProps {
  topic: Topic;
  onScan: (id: string) => Promise<string>;
  onDelete: (id: string) => void;
}

export function TopicCard({ topic, onScan, onDelete }: TopicCardProps) {
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const handleScan = async () => {
    if (isScanning || activeTaskId) return;
    setIsScanning(true);
    try {
      const taskId = await onScan(topic.id);
      setActiveTaskId(taskId);
    } catch {
      // error handled via toast in parent
    } finally {
      setIsScanning(false);
    }
  };

  const humanizedDate = topic.last_scan_at
    ? `Scanned ${formatDistanceToNow(new Date(topic.last_scan_at))} ago`
    : 'Never scanned';

  const isBusy = isScanning || !!activeTaskId;

  return (
    <div className="relative flex flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-sm hover:shadow-md hover:border-[var(--color-brand)] transition-all duration-200 group overflow-hidden">

      {/* Active indicator stripe */}
      {topic.is_active && (
        <div className="h-0.5 w-full bg-[var(--color-brand)] opacity-60" />
      )}

      {/* Body */}
      <div className="flex flex-col gap-3 p-5 flex-1">

        {/* Title row */}
        <div className="flex items-start justify-between gap-2">
          <Link href={`/topics/${topic.id}`} className="min-w-0 flex-1 group/link">
            <h3 className="text-sm font-semibold text-[var(--color-text)] group-hover/link:text-[var(--color-brand)] transition-colors line-clamp-2 leading-snug">
              {topic.raw_query}
            </h3>
          </Link>

          {/* Three-dot menu */}
          <div className="relative shrink-0" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Topic options"
              className={cn(
                'p-1.5 rounded-lg transition-colors flex items-center justify-center min-h-[32px] min-w-[32px]',
                'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text)]',
                'md:opacity-0 md:group-hover:opacity-100 focus:opacity-100',
                menuOpen && 'opacity-100 bg-[var(--color-surface-overlay)] text-[var(--color-text)]'
              )}
            >
              <MoreVertical className="h-4 w-4" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg overflow-hidden">
                <Link
                  href={`/topics/${topic.id}`}
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text)] transition-colors"
                >
                  <ExternalLink className="h-3.5 w-3.5 shrink-0" /> Open topic
                </Link>
                <Link
                  href={`/topics/${topic.id}/briefs`}
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-overlay)] hover:text-[var(--color-text)] transition-colors"
                >
                  <History className="h-3.5 w-3.5 shrink-0" /> Brief history
                </Link>
                <div className="h-px bg-[var(--color-border)] mx-3" />
                <button
                  onClick={() => { onDelete(topic.id); setMenuOpen(false); }}
                  className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-[var(--color-danger)] hover:bg-[var(--color-danger-subtle)] transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5 shrink-0" /> Delete
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-2">
          <div className={cn(
            'h-1.5 w-1.5 rounded-full shrink-0',
            topic.is_active ? 'bg-[var(--color-success)]' : 'bg-[var(--color-text-muted)]'
          )} />
          <span className="text-xs text-[var(--color-text-muted)]">
            {topic.is_active ? 'Active' : 'Paused'}
          </span>
          <span className="text-[var(--color-border-strong)] text-xs">·</span>
          <span className="text-xs text-[var(--color-text-muted)] truncate">{humanizedDate}</span>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 px-5 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface-overlay)]">
        <button
          onClick={handleScan}
          disabled={isBusy}
          className={cn(
            'inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all',
            isBusy
              ? 'text-[var(--color-text-muted)] cursor-wait'
              : 'bg-[var(--color-brand)] text-white hover:bg-[var(--color-brand-dark)] shadow-sm'
          )}
        >
          {isScanning
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : <Play className="h-3 w-3 fill-current" />
          }
          {activeTaskId ? 'Running…' : isScanning ? 'Starting…' : 'Scan Now'}
        </button>

        <ScanStatusBadge
          taskId={activeTaskId}
          onFinished={() => setActiveTaskId(null)}
        />
      </div>
    </div>
  );
}
