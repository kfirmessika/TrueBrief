"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface BriefContentProps {
  content: string;
}

export default function BriefContent({ content }: BriefContentProps) {
  return (
    <div className="max-w-[65ch] mx-auto">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h2 className="text-2xl font-black text-slate-900 mt-8 mb-3 tracking-tight">
              {children}
            </h2>
          ),
          h2: ({ children }) => (
            <h3 className="text-xl font-bold text-slate-800 mt-6 mb-2 tracking-tight">
              {children}
            </h3>
          ),
          h3: ({ children }) => (
            <h4 className="text-lg font-bold text-slate-800 mt-4 mb-2">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="text-slate-700 leading-relaxed mb-4 font-medium">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-inside space-y-2 mb-4 text-slate-700 font-medium ml-2">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside space-y-2 mb-4 text-slate-700 font-medium ml-2">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-600 underline underline-offset-4 font-bold hover:text-indigo-800 transition-colors"
            >
              {children}
            </a>
          ),
          strong: ({ children }) => (
            <strong className="font-black text-slate-900">{children}</strong>
          ),
          hr: () => <hr className="border-slate-200 my-8" />,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-indigo-200 pl-4 py-1 my-6 italic text-slate-600 bg-slate-50 rounded-r-xl">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="bg-slate-100 text-slate-900 px-1.5 py-0.5 rounded font-mono text-sm font-bold">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
