import Link from "next/link";
import { Inbox } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface BriefHistoryItem {
  topic_id: string;
  topic_name: string;
  brief_id: string;
  created_at: string;
  summary_preview: string;
}

export default async function HistoryPage() {
  const res = await apiFetch(`/briefs/history`);

  if (!res.ok) {
    throw new Error("Failed to load brief history");
  }

  const briefs: BriefHistoryItem[] = await res.json();

  // Group briefs by topic name
  const briefsByTopic = briefs.reduce((acc, brief) => {
    if (!acc[brief.topic_name]) {
      acc[brief.topic_name] = [];
    }
    acc[brief.topic_name].push(brief);
    return acc;
  }, {} as Record<string, BriefHistoryItem[]>);

  const topicNames = Object.keys(briefsByTopic).sort();

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <header className="mb-12">
        <h1 className="text-4xl font-black text-slate-900 tracking-tight mb-2">
          Brief History
        </h1>
        <p className="text-slate-500 font-medium text-lg">
          A complete timeline of all intelligence reports you've generated.
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
            Add a topic to get started generating intelligence reports.
          </p>
          <Link
            href="/topics"
            className="inline-flex items-center justify-center px-8 py-4 bg-indigo-600 text-white rounded-2xl font-black hover:bg-indigo-700 transition-all shadow-lg shadow-indigo-100 active:scale-95"
          >
            Browse Topics
          </Link>
        </div>
      ) : (
        <div className="space-y-12">
          {topicNames.map((topicName) => (
            <section key={topicName}>
              <h2 className="text-xl font-black text-slate-900 mb-6 tracking-tight">
                {topicName}
              </h2>
              <div className="grid gap-6">
                {briefsByTopic[topicName].map((brief) => (
                  <Link
                    key={brief.brief_id}
                    href={`/topics/${brief.topic_id}/briefs/${brief.brief_id}`}
                    className="block bg-white rounded-3xl border border-slate-100 p-8 shadow-sm hover:shadow-md transition-all group border-b-4 border-b-slate-50 hover:border-b-indigo-100"
                  >
                    <div className="mb-4">
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                        {new Date(brief.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric'
                        })}
                      </p>
                    </div>
                    <p className="text-slate-600 font-medium leading-relaxed line-clamp-3">
                      {brief.summary_preview}...
                    </p>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
