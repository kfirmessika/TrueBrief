import Link from "next/link";
import { ArrowLeft, Inbox } from "lucide-react";
import { apiFetch } from "@/lib/api";
import BriefCard from "@/components/briefs/BriefCard";
import { notFound } from "next/navigation";
import { Brief } from "@/lib/api";
import { FadeIn, StaggerList, StaggerItem } from "@/components/ui/motion";

export default async function BriefHistoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const res = await apiFetch(`/topics/${id}/briefs`);

  if (!res.ok) {
    if (res.status === 404) notFound();
    throw new Error("Failed to load briefs");
  }

  const briefs: Brief[] = await res.json();

  return (
    <FadeIn className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <Link
        href={`/topics/${id}`}
        className="inline-flex items-center gap-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-brand)] transition-colors mb-8 font-medium group"
      >
        <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to Topic
      </Link>

      <header className="mb-10">
        <h1 className="text-3xl font-bold text-[var(--color-text)] tracking-tight mb-1">
          Brief History
        </h1>
        <p className="text-sm text-[var(--color-text-secondary)]">
          A historical timeline of all intel reports generated for this topic.
        </p>
      </header>

      {briefs.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-surface-raised)] p-12 md:p-20 text-center">
          <div className="mb-6 inline-flex rounded-2xl bg-[var(--color-surface-overlay)] p-5">
            <Inbox className="h-10 w-10 text-[var(--color-text-muted)]" strokeWidth={1.5} />
          </div>
          <h2 className="text-xl font-bold text-[var(--color-text)] mb-2">No briefs yet</h2>
          <p className="text-sm text-[var(--color-text-secondary)] max-w-sm mx-auto mb-8 leading-relaxed">
            We haven't generated any intelligence reports for this topic yet. Trigger a manual scan to get started.
          </p>
          <Link
            href={`/topics/${id}`}
            className="inline-flex items-center justify-center px-6 py-2.5 bg-[var(--color-brand)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--color-brand-dark)] transition-colors shadow-sm"
          >
            Go to Topic Detail
          </Link>
        </div>
      ) : (
        <StaggerList className="grid gap-5">
          {briefs.map((brief) => (
            <StaggerItem key={brief.id}>
              <BriefCard brief={brief} topicId={id} />
            </StaggerItem>
          ))}
        </StaggerList>
      )}
    </FadeIn>
  );
}
