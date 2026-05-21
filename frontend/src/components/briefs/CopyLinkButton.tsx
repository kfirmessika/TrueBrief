"use client";

import { useState } from "react";
import { Share2, Check } from "lucide-react";

interface CopyLinkButtonProps {
  shareUrl?: string;
}

export default function CopyLinkButton({ shareUrl }: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const url = shareUrl ?? window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy: ", err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all shadow-sm ${
        copied
          ? "bg-[var(--color-success)] text-white"
          : "bg-[var(--color-text)] text-[var(--color-text-inverse)] hover:opacity-90"
      }`}
    >
      {copied ? (
        <><Check className="h-4 w-4" /> Copied!</>
      ) : (
        <><Share2 className="h-4 w-4" /> Share Brief</>
      )}
    </button>
  );
}
