import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { ArrowRight, Calendar } from "lucide-react";
import { Brief } from "@/lib/api";

interface BriefCardProps {
  brief: Brief;
  topicId: string;
}

export default function BriefCard({ brief, topicId }: BriefCardProps) {
  // Strip markdown symbols and truncate for preview
  const previewText = brief.content
    .replace(/[#*`_]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .substring(0, 200);

  return (
    <div className="bg-white rounded-3xl border border-slate-100 p-8 shadow-sm hover:shadow-md transition-all group border-b-4 border-b-slate-50 hover:border-b-indigo-100">
      <div className="flex flex-col md:flex-row justify-between items-start gap-4 mb-6">
        <div className="flex items-center gap-2 text-slate-400 font-bold text-xs uppercase tracking-widest">
          <Calendar className="h-3.5 w-3.5" />
          {formatDistanceToNow(new Date(brief.delivered_at))} ago
        </div>
      </div>
      
      <p className="text-slate-600 font-medium leading-relaxed mb-8 line-clamp-3">
        {previewText}...
      </p>

      <Link
        href={`/topics/${topicId}/briefs/${brief.id}`}
        className="flex items-center gap-2 text-indigo-600 font-black text-sm uppercase tracking-wider group-hover:gap-3 transition-all"
      >
        Read Full Brief <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
