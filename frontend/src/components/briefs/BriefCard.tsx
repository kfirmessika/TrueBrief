import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { ArrowRight, Calendar } from "lucide-react";
import { Brief } from "@/lib/api";

interface BriefCardProps {
  brief: Brief;
  topicId: string;
}

export default function BriefCard({ brief, topicId }: BriefCardProps) {
  const previewText = brief.content
    .replace(/[#*`_]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .substring(0, 200);

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6 shadow-sm hover:shadow-md hover:border-[var(--color-brand)] transition-all group">
      <div className="flex items-center gap-2 text-[var(--color-text-muted)] text-xs font-medium mb-4">
        <Calendar className="h-3.5 w-3.5" />
        {formatDistanceToNow(new Date(brief.delivered_at))} ago
      </div>

      <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed mb-6 line-clamp-3">
        {previewText}…
      </p>

      <Link
        href={`/topics/${topicId}/briefs/${brief.id}`}
        className="inline-flex items-center gap-2 text-[var(--color-brand)] text-xs font-semibold uppercase tracking-wider group-hover:gap-3 transition-all"
      >
        Read Full Brief <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
