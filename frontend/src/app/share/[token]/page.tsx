import { notFound } from 'next/navigation';
import Link from 'next/link';
import { format } from 'date-fns';
import { Zap, ArrowRight } from 'lucide-react';
import BriefContent from '@/components/briefs/BriefContent';

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
    description: `A noise-free intelligence brief on "${brief.topic_name}", powered by TrueBrief.`,
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
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Sign-up CTA banner */}
      <div className="bg-indigo-600 text-white rounded-2xl px-6 py-4 mb-10 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="bg-white/20 p-1.5 rounded-lg">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <p className="font-bold text-sm">
            Someone shared this brief with you.{' '}
            <span className="font-normal opacity-90">
              Get your own noise-free intelligence feed — free to start.
            </span>
          </p>
        </div>
        <Link
          href="/sign-up"
          className="shrink-0 flex items-center gap-1.5 bg-white text-indigo-700 px-4 py-2 rounded-xl text-sm font-black hover:bg-indigo-50 transition-colors"
        >
          Get Started Free <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <article className="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm p-8 md:p-16">
        <header className="mb-12 border-b border-slate-50 pb-12">
          <div className="inline-flex items-center px-3 py-1 bg-indigo-50 text-indigo-600 rounded-full text-xs font-black uppercase tracking-widest mb-6">
            Intelligence Brief
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tight leading-tight mb-4">
            {brief.topic_name}
          </h1>
          <p className="text-slate-400 font-bold uppercase tracking-widest text-xs">
            Delivered on {formattedDate}
          </p>
        </header>

        <BriefContent content={brief.content} />
      </article>

      <footer className="mt-16 text-center border-t border-slate-100 pt-12 space-y-4">
        <p className="text-slate-400 text-sm font-bold uppercase tracking-[0.2em]">
          End of Brief • TrueBrief Intelligence
        </p>
        <p className="text-slate-500 text-sm">
          Want briefs like this on your own topics?{' '}
          <Link href="/sign-up" className="text-indigo-600 font-bold hover:underline">
            Start for free →
          </Link>
        </p>
      </footer>
    </div>
  );
}
