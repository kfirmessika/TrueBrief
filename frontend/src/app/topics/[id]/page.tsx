import { apiFetch } from "@/lib/api";
import Link from 'next/link';
import { ArrowLeft, Clock, History, Play, Trash2 } from 'lucide-react';
import { notFound } from 'next/navigation';
import { formatDistanceToNow } from 'date-fns';

export default async function TopicDetailPage({ params }: { params: { id: string } }) {
  const res = await apiFetch(`/topics/${params.id}`);
  
  if (!res.ok) {
    if (res.status === 404) notFound();
    throw new Error("Failed to load topic");
  }

  const topic = await res.json();

  const humanizedDate = topic.last_scan_at 
    ? `${formatDistanceToNow(new Date(topic.last_scan_at))} ago`
    : 'Never scanned';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link href="/dashboard" className="flex items-center gap-2 text-slate-500 hover:text-indigo-600 transition-colors mb-8 group">
        <ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition-transform" /> Back to Dashboard
      </Link>

      <div className="flex flex-col md:flex-row justify-between items-start gap-8 mb-12">
        <div className="flex-grow">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-4xl font-black text-slate-900 tracking-tight">{topic.raw_query}</h1>
            <div className={`h-2.5 w-2.5 rounded-full ${topic.is_active ? 'bg-green-500' : 'bg-slate-300'}`} />
          </div>
          <div className="flex flex-wrap gap-6 text-sm font-bold text-slate-400 uppercase tracking-widest">
            <span className="flex items-center gap-1.5"><Clock className="h-4 w-4" /> Last scan: {humanizedDate}</span>
            <span className="flex items-center gap-1.5"><History className="h-4 w-4" /> {topic.frequency} interval</span>
          </div>
        </div>
        
        <div className="flex gap-3 w-full md:w-auto">
          <Link 
            href={`/topics/${params.id}/briefs`} 
            className="flex-grow md:flex-none flex items-center justify-center gap-2 px-6 py-3 border-2 border-slate-200 rounded-2xl font-black hover:bg-slate-50 transition-all text-slate-700 active:scale-95"
          >
            <History className="h-5 w-5" /> View Briefs
          </Link>
          <button className="flex-grow md:flex-none flex items-center justify-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-2xl font-black hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 active:scale-95">
            <Play className="h-5 w-5 fill-white" /> Manual Scan
          </button>
        </div>
      </div>

      <div className="bg-white rounded-[2.5rem] p-12 text-center border border-slate-100 shadow-sm">
        <div className="bg-slate-50 p-6 rounded-[2rem] w-fit mx-auto mb-8">
          <History className="h-12 w-12 text-slate-300" />
        </div>
        <h2 className="text-3xl font-black text-slate-900 mb-4 tracking-tight">Intelligence Feed</h2>
        <p className="text-slate-500 max-w-lg mx-auto mb-10 text-lg font-medium leading-relaxed">
          Brief content rendering is arriving in Step 3.9. For now, you can trigger manual scans and manage your tracking parameters.
        </p>
        
        <div className="pt-10 border-t border-slate-50 flex justify-center">
          <button className="text-red-500 font-bold hover:text-red-700 transition-colors flex items-center gap-2">
            <Trash2 className="h-5 w-5" /> Stop tracking this topic
          </button>
        </div>
      </div>
    </div>
  );
}
