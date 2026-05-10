"use client";

import { useState } from "react";
import { Share2, Check } from "lucide-react";

export default function CopyLinkButton() {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy: ", err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold transition-all text-sm shadow-sm ${
        copied
          ? "bg-green-500 text-white shadow-green-100"
          : "bg-slate-900 text-white hover:bg-slate-800 shadow-slate-200"
      }`}
    >
      {copied ? (
        <>
          <Check className="h-4 w-4" /> Copied!
        </>
      ) : (
        <>
          <Share2 className="h-4 w-4" /> Copy Link
        </>
      )}
    </button>
  );
}
