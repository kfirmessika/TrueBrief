'use client';

import { Zap, ArrowRight } from 'lucide-react';
import Link from 'next/link';

interface UpgradeBannerProps {
  currentCount: number;
  maxTopics: number;
}

export function UpgradeBanner({ currentCount, maxTopics }: UpgradeBannerProps) {
  return (
    <div className="bg-gradient-to-r from-indigo-600 to-violet-700 rounded-3xl p-8 text-white shadow-xl shadow-indigo-200 flex flex-col md:flex-row items-center justify-between gap-6 overflow-hidden relative group">
      <div className="absolute -right-8 -top-8 bg-white/10 rounded-full w-32 h-32 sm:w-48 sm:h-48 blur-3xl group-hover:bg-white/20 transition-all duration-700" />
      
      <div className="relative z-10">
        <div className="flex items-center gap-2 bg-white/20 px-3 py-1 rounded-full text-xs font-black uppercase tracking-widest w-fit mb-4">
          <Zap className="h-3 w-3 fill-white" /> Limit Reached
        </div>
        <h3 className="text-2xl font-black mb-2 leading-tight">
          You're using {currentCount} of {maxTopics} Free Topics
        </h3>
        <p className="text-indigo-100 font-medium max-w-md">
          Upgrade to a Pro or Power plan to track unlimited topics and get faster intelligence scans.
        </p>
      </div>

      <Link
        href="/pricing"
        className="relative z-10 flex items-center gap-2 bg-white text-indigo-600 px-8 py-4 rounded-2xl font-black hover:bg-indigo-50 transition-all shadow-lg active:scale-95 shrink-0"
      >
        Upgrade Now <ArrowRight className="h-5 w-5" />
      </Link>
    </div>
  );
}
