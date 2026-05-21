import Link from "next/link";
import { Inbox } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { FadeIn, StaggerList, StaggerItem } from "@/components/ui/motion";
import { formatDistanceToNow } from "date-fns";

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

  const briefsByTopic = briefs.reduce((acc, brief) => {
    if (!acc[brief.topic_name]) acc[brief.topic_name] = [];
    acc[brief.topic_name].push(brief);
    return acc;
  }, {} as Record<string, BriefHistoryItem[]>);

  const topicNames = Object.keys(briefsByTopic).sort();

  return (
    <FadeIn className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <header className="mb-12">
        <h1 className="text-3xl font-bold text-[var(--color-text)] tracking-tight mb-1">
          Brief History
        </h1>
        <p className="text-sm text-[var(--color-text-secondary)]">
          A complete timeline of all intelligence reports you've generated.
        </p>
      </header>

      {briefs.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-surface-raised)] p-12 md:p-20 text-center">
          <div className="mb-6 inline-flex rounded-2xl bg-[var(--color-surface-overlay)] p-5">
            <Inbox className="h-10 w-10 text-[var(--color-text-muted)]" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-bold text-[var(--color-text)] mb-2">No briefs yet</h2>
          <p className="text-sm text-[var(--color-text-secondary)] max-w-sm mx-auto mb-8 leading-relaxed">
            Add a topic to start generating intelligence reports.
          </p>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center px-6 py-2.5 bg-[var(--color-brand)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-colors shadow-sm"
          >
            Go to Dashboard
          </Link>
        </div>
      ) : (
        <div className="space-y-10">
          {topicNames.map((topicName) => (
            <section key={topicName}>
              <h2 className="text-sm font-semibold text-[var(--color-text-muted)] uppercase tracking-widest mb-4">
                {topicName}
              </h2>
              <StaggerList className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] divide-y divide-[var(--color-border)] overflow-hidden">
                {briefsByTopic[topicName].map((brief) => (
                  <StaggerItem key={brief.brief_id}>
                    <Link
                      href={`/topics/${brief.topic_id}/briefs/${brief.brief_id}`}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-4 hover:bg-[var(--color-surface-overlay)] transition-colors group"
                    >
                      <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed line-clamp-2 flex-1">
                        {brief.summary_preview}
                      </p>
                      <span className="shrink-0 text-xs text-[var(--color-text-muted)] group-hover:text-[var(--color-brand)] transition-colors">
                        {formatDistanceToNow(new Date(brief.created_at))} ago
                      </span>
                    </Link>
                  </StaggerItem>
                ))}
              </StaggerList>
            </section>
          ))}
        </div>
      )}
    </FadeIn>
  );
}
