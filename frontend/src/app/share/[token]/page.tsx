import { notFound } from 'next/navigation';
import Link from 'next/link';
import { format } from 'date-fns';
import { Zap, ArrowRight } from 'lucide-react';
import BriefContent from '@/components/briefs/BriefContent';
import { FadeIn } from '@/components/ui/motion';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface SharedBrief {
  brief_id: string;
  content: string;
  delivered_at: string;
  topic_name: string;
}

export async function generateMetadata({ params }: { params: { token: string } }) {
  const res = await fetch(`${API_BASE_URL}/share/${params.token}`, { cache: 'no-store' });
  if (!res.ok) return { title: 'Brief Not Found | TrueBrief' };
  const brief: SharedBrief = await res.json();
  return {
    title: `${brief.topic_name} — Intelligence Brief | TrueBrief`,
    description: `A concise, noise-free intelligence brief on "${brief.topic_name}", powered by TrueBrief.`,
  };
}

export default async function SharePage({ params }: { params: { token: string } }) {
  const res = await fetch(`${API_BASE_URL}/share/${params.token}`, { cache: 'no-store' });

  if (!res.ok) {
    if (res.status === 404) notFound();
    throw new Error('Failed to load shared brief');
  }

  const brief: SharedBrief = await res.json();
  const formattedDate = format(new Date(brief.delivered_at), 'MMMM d, yyyy · h:mm a');

  return (
    <FadeIn className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Sign-up banner */}
      <div className="rounded-xl px-5 py-4 mb-8 flex flex-col sm:flex-row items-center justify-between gap-4"
        style={{ background: 'oklch(0.55 0.22 264)' }}>
        <div className="flex items-center gap-3">
          <div className="bg-white/20 p-1.5 rounded-lg shrink-0">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <p className="text-sm text-white font-medium">
            Someone shared this brief with you.{' '}
            <span className="opacity-80 font-normal">
              Get your own personalised news feed — free to start.
            </span>
          </p>
        </div>
        <Link
          href="/sign-up"
          className="shrink-0 flex items-center gap-1.5 bg-white text-[var(--color-brand)] px-4 py-2 rounded-lg text-sm font-semibold hover:bg-white/90 transition-colors"
        >
          Get Started Free <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <article className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-sm p-6 md:p-12">
        <header className="mb-10 border-b border-[var(--color-border)] pb-10">
          <div className="inline-flex items-center px-3 py-1 bg-[var(--color-brand-subtle)] text-[var(--color-brand)] rounded-full text-xs font-semibold uppercase tracking-widest mb-5">
            Intelligence Brief
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-[var(--color-text)] tracking-tight leading-tight mb-3">
            {brief.topic_name}
          </h1>
          <p className="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-widest">
            Delivered on {formattedDate}
          </p>
        </header>

        <BriefContent content={brief.content} />
      </article>

      <footer className="mt-12 text-center border-t border-[var(--color-border)] pt-8 space-y-3">
        <p className="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-[0.2em]">
          End of Brief · TrueBrief
        </p>
        <p className="text-sm text-[var(--color-text-secondary)]">
          Want briefs like this on topics you choose?{' '}
          <Link href="/sign-up" className="text-[var(--color-brand)] font-semibold hover:underline">
            Start for free →
          </Link>
        </p>
      </footer>
    </FadeIn>
  );
}
