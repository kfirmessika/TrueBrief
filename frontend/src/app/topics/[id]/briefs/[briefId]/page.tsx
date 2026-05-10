import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch, Brief, Topic } from "@/lib/api";
import { notFound } from "next/navigation";
import { format } from "date-fns";
import BriefContent from "@/components/briefs/BriefContent";
import CopyLinkButton from "@/components/briefs/CopyLinkButton";

export default async function BriefDetailPage({
  params,
}: {
  params: { id: string; briefId: string };
}) {
  // Parallel fetch for brief data and topic metadata
  const [briefRes, topicRes] = await Promise.all([
    apiFetch(`/briefs/${params.briefId}`),
    apiFetch(`/topics/${params.id}`),
  ]);

  if (!briefRes.ok) {
    if (briefRes.status === 404) notFound();
    throw new Error("Failed to load brief");
  }

  const brief: Brief = await briefRes.json();
  const topic: Topic = topicRes.ok ? await topicRes.json() : null;

  const formattedDate = format(
    new Date(brief.delivered_at),
    "MMMM d, yyyy · h:mm a"
  );

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 mb-12">
        <Link
          href={`/topics/${params.id}/briefs`}
          className="flex items-center gap-2 text-slate-500 hover:text-indigo-600 transition-colors group font-bold"
        >
          <ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition-transform" />{" "}
          Back to History
        </Link>
        <CopyLinkButton />
      </div>

      <article className="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm p-8 md:p-16">
        <header className="mb-12 border-b border-slate-50 pb-12">
          <div className="inline-flex items-center px-3 py-1 bg-indigo-50 text-indigo-600 rounded-full text-xs font-black uppercase tracking-widest mb-6">
            Intelligence Brief
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tight leading-tight mb-4">
            {topic ? topic.raw_query : "Topic Report"}
          </h1>
          <p className="text-slate-400 font-bold uppercase tracking-widest text-xs">
            Delivered on {formattedDate}
          </p>
        </header>

        <BriefContent content={brief.content} />
      </article>

      <footer className="mt-16 text-center border-t border-slate-100 pt-12">
        <p className="text-slate-400 text-sm font-bold uppercase tracking-[0.2em]">
          End of Brief • TrueBrief Intelligence
        </p>
      </footer>
    </div>
  );
}
