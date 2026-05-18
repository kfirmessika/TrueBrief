'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';

export type TabId = 'briefs' | 'stories' | 'insights';

interface Tab {
  id: TabId;
  label: string;
  count?: number;
}

interface TopicTabsProps {
  tabs: Tab[];
  children: (activeTab: TabId) => React.ReactNode;
  defaultTab?: TabId;
}

export default function TopicTabs({ tabs, children, defaultTab = 'briefs' }: TopicTabsProps) {
  const [active, setActive] = useState<TabId>(defaultTab);

  return (
    <div>
      {/* Tab bar */}
      <div className="border-b border-[var(--color-border)] mb-6">
        <nav className="-mb-px flex gap-0" aria-label="Topic sections">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActive(tab.id)}
              className={cn(
                'px-4 py-3 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap',
                active === tab.id
                  ? 'border-[var(--color-brand)] text-[var(--color-brand)]'
                  : 'border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:border-[var(--color-border-strong)]'
              )}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span className={cn(
                  'ml-2 text-xs rounded-full px-1.5 py-0.5',
                  active === tab.id
                    ? 'bg-[var(--color-brand-subtle)] text-[var(--color-brand)]'
                    : 'bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)]'
                )}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {children(active)}
    </div>
  );
}
