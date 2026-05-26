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
  panels: Record<TabId, React.ReactNode>;
  defaultTab?: TabId;
}

export default function TopicTabs({ tabs, panels, defaultTab = 'briefs' }: TopicTabsProps) {
  const [active, setActive] = useState<TabId>(defaultTab);

  return (
    <div>
      {/* Tab bar — pill style */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-[var(--color-surface-overlay)] w-fit mb-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150 whitespace-nowrap',
              active === tab.id
                ? 'bg-[var(--color-surface)] text-[var(--color-text)] shadow-sm'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]'
            )}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className={cn(
                'text-[11px] font-semibold rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center leading-none',
                active === tab.id
                  ? 'bg-[var(--color-brand-subtle)] text-[var(--color-brand)]'
                  : 'bg-[var(--color-border)] text-[var(--color-text-muted)]'
              )}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {panels[active]}
    </div>
  );
}
