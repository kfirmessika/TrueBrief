import Link from "next/link";
import { ArrowLeft, Inbox } from "lucide-react";
import { apiFetch } from "@/lib/api";
import BriefCard from "@/components/briefs/BriefCard";
import { notFound } from "next/navigation";
import { Brief } from "@/lib/api";

export default async function BriefHistoryPage({
  params,
}: {
  params: { id: string };
}) {
  const res = await apiFetch(`/topics/${params.id}/briefs`);

  if (!res.ok) {
    if (res.status === 404) notFound();
    throw new Error("Failed to load briefs");
  }

  const briefs: Brief[] = await res.json();

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link
        href={`/topics/${params.id}`}
        className="flex items-center gap-2 text-slate-500 hover:text-indigo-600 transition-colors mb-8 group font-bold"
      >
        <ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition-transform" />{" "}
        Back to Topic
      </Link>

      <header className="mb-12">
        <h1 className="text-4xl font-black text-slate-900 tracking-tight mb-2">
          Brief History
        </h1>
        <p className="text-slate-500 font-medium text-lg">
          A historical timeline of all intel reports generated for this topic.
        </p>
      </header>

      {briefs.length === 0 ? (
        <div className="bg-white rounded-[2.5rem] p-16 text-center border border-slate-100 shadow-sm">
          <div className="bg-slate-50 p-6 rounded-[2rem] w-fit mx-auto mb-8">
            <Inbox className="h-12 w-12 text-slate-300" />
          </div>
          <h2 className="text-2xl font-black text-slate-900 mb-4 tracking-tight">
            No briefs yet
          </h2>
          <p className="text-slate-500 max-w-sm mx-auto mb-10 text-lg font-medium leading-relaxed">
            We haven't generated any intelligence reports for this topic yet.
            Trigger a manual scan to get started.
          </p>
          <Link
            href={`/topics/${params.id}`}
            className="inline-flex items-center justify-center px-8 py-4 bg-indigo-600 text-white rounded-2xl font-black hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 active:scale-95"
          >
            Go to Topic Detail
          </Link>
        </div>
      ) : (
        <div className="grid gap-6">
          {briefs.map((brief) => (
            <BriefCard key={brief.id} brief={brief} topicId={params.id} />
          ))}
        </div>
      )}
    </div>
  );
}
