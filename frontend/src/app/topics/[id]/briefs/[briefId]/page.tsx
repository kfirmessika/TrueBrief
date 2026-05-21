import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { apiFetch, Brief, Topic } from "@/lib/api";
import { notFound } from "next/navigation";
import { format } from "date-fns";
import { headers } from "next/headers";
import BriefContent from "@/components/briefs/BriefContent";
import CopyLinkButton from "@/components/briefs/CopyLinkButton";
import { FadeIn } from "@/components/ui/motion";

export default async function BriefDetailPage({
  params,
}: {
  params: { id: string; briefId: string };
}) {
  const headersList = await headers();
  const host = headersList.get('host') ?? 'localhost:3000';
  const protocol = host.startsWith('localhost') ? 'http' : 'https';
  const shareUrl = `${protocol}://${host}/share/${params.briefId}`;

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

  const formattedDate = format(new Date(brief.delivered_at), "MMMM d, yyyy · h:mm a");

  return (
    <FadeIn className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-10">
        <Link
          href={`/topics/${params.id}/briefs`}
          className="inline-flex items-center gap-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-brand)] transition-colors font-medium group"
        >
          <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to History
        </Link>
        <CopyLinkButton shareUrl={shareUrl} />
      </div>

      <article className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] shadow-sm p-6 md:p-12">
        <header className="mb-10 border-b border-[var(--color-border)] pb-10">
          <div className="inline-flex items-center px-3 py-1 bg-[var(--color-brand-subtle)] text-[var(--color-brand)] rounded-full text-xs font-semibold uppercase tracking-widest mb-5">
            Intelligence Brief
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-[var(--color-text)] tracking-tight leading-tight mb-3">
            {topic ? topic.raw_query : "Topic Report"}
          </h1>
          <p className="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-widest">
            Delivered on {formattedDate}
          </p>
        </header>

        <BriefContent content={brief.content} />
      </article>

      <footer className="mt-12 text-center border-t border-[var(--color-border)] pt-8">
        <p className="text-xs text-[var(--color-text-muted)] font-medium uppercase tracking-[0.2em]">
          End of Brief • TrueBrief Intelligence
        </p>
      </footer>
    </FadeIn>
  );
}
