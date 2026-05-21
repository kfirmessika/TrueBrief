'use client';

import { Zap, ArrowRight } from 'lucide-react';
import Link from 'next/link';

interface UpgradeBannerProps {
  currentCount: number;
  maxTopics: number;
}

export function UpgradeBanner({ currentCount, maxTopics }: UpgradeBannerProps) {
  return (
    <div className="relative rounded-2xl p-6 md:p-8 overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-6"
      style={{ background: 'linear-gradient(135deg, oklch(0.55 0.22 264), oklch(0.50 0.20 290))' }}>
      <div className="absolute -right-8 -top-8 rounded-full w-48 h-48 blur-3xl opacity-20 bg-white pointer-events-none" />

      <div className="relative z-10">
        <div className="inline-flex items-center gap-1.5 bg-white/20 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest text-white mb-3">
          <Zap className="h-3 w-3 fill-white" /> Limit Reached
        </div>
        <h3 className="text-xl font-bold text-white mb-1 leading-tight">
          You're using {currentCount} of {maxTopics} free topics
        </h3>
        <p className="text-white/80 text-sm max-w-md">
          Upgrade to Pro to track unlimited topics and get faster intelligence scans.
        </p>
      </div>

      <Link
        href="/settings"
        className="relative z-10 inline-flex items-center gap-2 bg-white text-[var(--color-brand)] px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-white/90 transition-all shadow-sm shrink-0 active:scale-95"
      >
        Upgrade Now <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
